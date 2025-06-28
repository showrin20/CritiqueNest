from sqlalchemy import create_engine, Column, Integer, String, Float, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# Database Configuration
DATABASE_URL = "mysql+mysqlconnector://username:password@localhost/critiquenest"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Database Models
class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, index=True)
    email = Column(String(100), unique=True, index=True)
    hashed_password = Column(String(255))

class Media(Base):
    __tablename__ = "media"
    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(100), index=True)
    type = Column(String(20))  # e.g., book, movie, web_series
    image_url = Column(String(255))  # URL for media image

class Review(Base):
    __tablename__ = "reviews"
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    media_id = Column(Integer, ForeignKey("media.id"))
    rating = Column(Float)
    comment = Column(String(500))

# Create tables
Base.metadata.create_all(bind=engine)