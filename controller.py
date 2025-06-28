from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlalchemy.orm import Session
from typing import List, Optional
from models import SessionLocal, User, Media, Review
from passlib.context import CryptContext
from jose import JWTError, jwt
from datetime import datetime, timedelta
import os

app = FastAPI(title="CritiqueNest Backend")

# JWT Configuration
SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")  # Replace with secure key in production
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Password hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2 scheme
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="login")

# Pydantic Models
class UserCreate(BaseModel):
    username: str
    email: str
    password: str

class UserResponse(BaseModel):
    id: int
    username: str
    email: str

    class Config:
        orm_mode = True

class ReviewCreate(BaseModel):
    media_id: Optional[int] = None
    media_title: Optional[str] = None
    image_url: Optional[str] = None
    type: Optional[str] = None
    rating: float
    comment: str

class ReviewResponse(BaseModel):
    id: int
    user_id: int
    media_id: int
    media_title: str
    image_url: str
    type: str
    rating: float
    comment: str

    class Config:
        orm_mode = True

class Token(BaseModel):
    access_token: str
    token_type: str

# Dependency for DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# JWT Functions
def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt

async def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: int = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
    return user

# Authentication Endpoints
@app.post("/signup", response_model=UserResponse)
async def signup(user: UserCreate, db: Session = Depends(get_db)):
    # Check if username or email exists
    if db.query(User).filter(User.username == user.username).first():
        raise HTTPException(status_code=400, detail="Username already registered")
    if db.query(User).filter(User.email == user.email).first():
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Hash password and create user
    hashed_password = pwd_context.hash(user.password)
    db_user = User(username=user.username, email=user.email, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

@app.post("/login", response_model=Token)
async def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(User).filter(User.username == form_data.username).first()
    if not user or not pwd_context.verify(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect username or password")
    
    access_token = create_access_token({"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer"}

# Review Endpoints
@app.post("/reviews/", response_model=ReviewResponse)
async def create_review(review: ReviewCreate, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    # Validate input
    if not review.media_id and not (review.media_title and review.image_url and review.type):
        raise HTTPException(status_code=400, detail="Either media_id or (media_title, image_url, type) must be provided")
    if review.type and review.type not in ["book", "movie", "web_series"]:
        raise HTTPException(status_code=400, detail="Type must be one of: book, movie, web_series")
    if review.rating < 0 or review.rating > 5:
        raise HTTPException(status_code=400, detail="Rating must be between 0 and 5")

    # Check or create media
    if review.media_id:
        media = db.query(Media).filter(Media.id == review.media_id).first()
        if not media:
            raise HTTPException(status_code=404, detail="Media not found")
    else:
        media = Media(title=review.media_title, image_url=review.image_url, type=review.type)
        db.add(media)
        db.commit()
        db.refresh(media)
    
    # Create review
    db_review = Review(
        user_id=current_user.id,
        media_id=media.id,
        rating=review.rating,
        comment=review.comment
    )
    db.add(db_review)
    db.commit()
    db.refresh(db_review)
    return ReviewResponse(
        id=db_review.id,
        user_id=db_review.user_id,
        media_id=db_review.media_id,
        media_title=media.title,
        image_url=media.image_url,
        type=media.type,
        rating=db_review.rating,
        comment=db_review.comment
    )

@app.get("/reviews/", response_model=List[ReviewResponse])
async def get_all_reviews(db: Session = Depends(get_db)):
    reviews = db.query(Review).join(Media).all()
    if not reviews:
        raise HTTPException(status_code=404, detail="No reviews found")
    return [
        ReviewResponse(
            id=review.id,
            user_id=review.user_id,
            media_id=review.media_id,
            media_title=review.media.title,
            image_url=review.media.image_url,
            type=review.media.type,
            rating=review.rating,
            comment=review.comment
        ) for review in reviews
    ]

@app.get("/reviews/{review_id}", response_model=ReviewResponse)
async def get_review(review_id: int, db: Session = Depends(get_db)):
    review = db.query(Review).join(Media).filter(Review.id == review_id).first()
    if not review:
        raise HTTPException(status_code=404, detail="Review not found")
    return ReviewResponse(
        id=review.id,
        user_id=review.user_id,
        media_id=review.media_id,
        media_title=review.media.title,
        image_url=review.media.image_url,
        type=review.media.type,
        rating=review.rating,
        comment=review.comment
    )

@app.get("/reviews/media/{media_id}", response_model=List[ReviewResponse])
async def get_reviews_by_media(media_id: int, db: Session = Depends(get_db)):
    reviews = db.query(Review).join(Media).filter(Review.media_id == media_id).all()
    if not reviews:
        raise HTTPException(status_code=404, detail="No reviews found for this media")
    return [
        ReviewResponse(
            id=review.id,
            user_id=review.user_id,
            media_id=review.media_id,
            media_title=review.media.title,
            image_url=review.media.image_url,
            type=review.media.type,
            rating=review.rating,
            comment=review.comment
        ) for review in reviews
    ]