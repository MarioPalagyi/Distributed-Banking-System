from sqlalchemy import create_engine, ForeignKey, Column, String, Integer, CHAR, DateTime, FLOAT, BOOLEAN, Enum
from datetime import datetime
import enum
from sqlalchemy.orm import sessionmaker, declarative_base

Base = declarative_base()

engine = create_engine("sqlite:///bank_system.db", connect_args={"check_same_thread":False}) # check_same_thread - SQLite specific; allow Flask multiple threads

Session = sessionmaker(bind=engine)