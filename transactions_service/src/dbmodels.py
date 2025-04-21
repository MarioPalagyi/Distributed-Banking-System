from sqlalchemy import Column, String, Float, Boolean, DateTime, ForeignKey, Enum, Integer
from sqlalchemy.orm import relationship
from datetime import datetime
import enum
from setupdb import Base

class TransactionStatus(enum.Enum):
    submitted = "submitted"
    accepted = "accepted"
    rejected = "rejected"

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column("id", Integer, primary_key=True, index=True)
    customer = Column("customer", String, nullable=False) # nullable = False for not allowing NULL values
    timestamp = Column("timestamp", DateTime, default = datetime.utcnow) # utcnow instead of now: gives Universal Coordinated Time
    status = Column("status", Enum(TransactionStatus), default = TransactionStatus.submitted)
    vendor_id = Column("vendor_id", String, nullable=False)
    amount = Column("amount", Float, nullable=False)

    results = relationship("Result", back_populates="transaction")

class Result(Base):
    __tablename__ = "results"

    id = Column("id", Integer, primary_key=True, index=True)
    transaction_id = Column("transaction_id", Integer, ForeignKey("transactions.id"), nullable=False) # is a foreign key of the transactions db's id
    timestamp = Column("timestamp", DateTime, default = datetime.utcnow)
    is_fraudulent = Column("is_fraudulent", Boolean)
    confidence = Column("confidence", Float, nullable=False)
    
    transaction = relationship("Transaction", back_populates="results")