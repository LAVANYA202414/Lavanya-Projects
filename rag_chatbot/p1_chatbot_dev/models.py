from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Enum, Text, Boolean
from database import Base
from datetime import datetime, timezone
from sqlalchemy import JSON
from typing import Tuple

class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    session_id = Column(String(255), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    active = Column(Boolean, default=True)


class Messages(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)

    conversation_id = Column(Integer,ForeignKey("conversations.id"), nullable=False)
    role = Column(
        Enum("human", "ai", name="message_role_enum"),
        nullable=False
    )
    content = Column(
        Text,
        nullable=False
    )
    
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    






    '''
    Conversations -> conversation_id
CREATE TABLE conversations (
id BIGINT PRIMARY KEY AUTO_INCREMENT,
session_id VARCHAR(255) NOT NULL,


created_at DATETIME DEFAULT CURRENT_TIMESTAMP,


INDEX(session_id)

);
'''



'''
messages
CREATE TABLE messages (
id BIGINT PRIMARY KEY AUTO_INCREMENT,
conversation_id BIGINT NOT NULL, (foreign key)

role ENUM('human', 'ai') NOT NULL,

content LONGTEXT NOT NULL,
created_at DATETIME DEFAULT CURRENT_TIMESTAMP,

INDEX(conversation_id),

FOREIGN KEY (conversation_id)
REFERENCES conversations(id)
ON DELETE CASCADE

);
'''