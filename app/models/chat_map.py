from sqlalchemy import Column, String, Integer
from app.db.base import Base
import uuid

class ChatMap(Base):
    __tablename__ = "chat_map"
    id = Column(String, primary_key=True, default=lambda: uuid.uuid4().hex)
    user_id = Column(String, nullable=False, index=True)
    chat_id = Column(String, nullable=False)
    
    def to_dict(self): 
        return {
            "id": self.id, 
            "user_id": self.user_id, 
            "chat_id": self.chat_id
        }
