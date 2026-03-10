from sqlalchemy import create_engine, Column, Integer, String, DateTime, Boolean, Text, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = 'users'
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    username = Column(String(100))
    first_name = Column(String(100))
    last_name = Column(String(100))
    registered_at = Column(DateTime, default=datetime.datetime.utcnow)
    is_blocked = Column(Boolean, default=False)
    total_tickets = Column(Integer, default=0)
    
    tickets = relationship("Ticket", back_populates="user")
    
class Ticket(Base):
    __tablename__ = 'tickets'
    
    id = Column(Integer, primary_key=True)
    ticket_number = Column(String(20), unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey('users.id'))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    status = Column(String(20), default='open')  # open, in_progress, closed, rejected
    category = Column(String(50))
    description = Column(Text)
    proof = Column(Text)  # Ссылки на доказательства
    assigned_to = Column(Integer, nullable=True)  # ID админа в Telegram
    closed_at = Column(DateTime, nullable=True)
    closed_by = Column(Integer, nullable=True)
    
    user = relationship("User", back_populates="tickets")
    messages = relationship("TicketMessage", back_populates="ticket")
    
class TicketMessage(Base):
    __tablename__ = 'ticket_messages'
    
    id = Column(Integer, primary_key=True)
    ticket_id = Column(Integer, ForeignKey('tickets.id'))
    sender_id = Column(Integer)  # Telegram ID отправителя
    sender_name = Column(String(100))
    message = Column(Text)
    sent_at = Column(DateTime, default=datetime.datetime.utcnow)
    is_from_admin = Column(Boolean, default=False)
    
    ticket = relationship("Ticket", back_populates="messages")

class BanLog(Base):
    __tablename__ = 'ban_logs'
    
    id = Column(Integer, primary_key=True)
    player_nick = Column(String(100))
    telegram_id = Column(Integer, nullable=True)
    reason = Column(String(500))
    banned_by = Column(Integer)  # Telegram ID админа
    banned_at = Column(DateTime, default=datetime.datetime.utcnow)
    duration_days = Column(Integer, default=0)  # 0 = навсегда

def init_db(db_url):
    engine = create_engine(db_url)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    return Session()