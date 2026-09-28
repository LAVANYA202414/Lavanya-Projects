from pydantic_settings import BaseSettings

class Setting(BaseSettings):
    POSTGRES_USER: str
    POSTGRES_PASSWORD: str
    POSTGRES_HOST: str
    POSTGRES_PORT: int
    POSTGRES_DB : str

    # WhatsApp Cloud API
    WHATSAPP_ACCESS_TOKEN: str
    PHONE_NUMBER_ID: str
    WHATSAPP_VERIFY_TOKEN: str
    BASE_URL: str
    WABA_ID: str
    
    # JWT KEYS
    JWT_SECRET_KEY : str
    JWT_REFRESH_SECRET_KEY : str
    ACCESS_TOKEN_EXPIRE_MINUTES: int
    REFRESH_TOKEN_EXPIRE_MINUTES: int
    ALGORITHM: str

    # SMPT KEYS
    FROM_EMAIL : str
    APP_PASSWORD: str
    HOSTNAME : str
    PORT: int
    
    # LOCAL HOST URL KEY
    HOST_URL: str
    
    # Ollama model
    OLLAMA_DEFAULT_MODEL : str

    class Config:
        env_file = ".env"

settings = Setting()

"""
1. Tenant & Business Domain  
tenant.py
- tenants : Done
- tenant_kyc : Pending

business.py
- businesses : done
- business_users : done
- business_languages: done
- business_verifications : done

💳 2. Subscription Domain
subscription.py
- plans : done
- business_subscriptions : done

👤 3. User & Auth Domain
user.py
- users: done
- user_sessions : done
- user_verifications : done

👥 4. Staff Domain
staff.py
- staff_members: done
- staff_services: done
- staff_availability : done

🛍️ 5. Services Domain
service.py
- services: done

📅 6. Booking Domain (IMPORTANT CORE)
booking.py
- bookings: done
- booking_sessions: done
- booking_answers: done
- booking_forms: done
- booking_questions: done
- booking_question_translations: done

💬 7. WhatsApp / Chat Domain
whatsapp.py
- whatsapp_accounts: done
- conversations: done
- messages: done
- message_templates: done

🌍 8. Contact & Language Domain
contact.py
- contacts: done
- business_contacts: done

translation.py
- languages: done
- translations: done

💰 9. Payment Domain
payment.py
- payments: done
- payment_transactions: done

📢 10. Campaign / Marketing Domain
campaign.py
- campaigns
- campaign_recipients


🛠️ 11. Support System Domain
support.py
- support_tickets
- support_ticket_messages
- support_ticket_attachments


🔔 12. Notification Domain
notification.py
- notification_templates
- notification_logs


🔗 13. Webhook Domain
webhook.py
- webhook_subscriptions: done
- webhook_deliveries : done


🔐 14. Security & Audit Domain
security.py
- login_history
- security_events
- audit_logs
- api_keys : done


⚡ 15. Realtime / Socket Domain
realtime.py  (or socket.py)
- user_socket_sessions
- socket_rooms
- socket_events

"""

"""
Amazon S3
        │
Medical PDFs
        │
        ▼
Document Processing
(chunking + OCR if needed)
        │
        ▼
Embedding Model
        │
        ▼
Qdrant
(Dense + Sparse + Metadata)
        │
        ▼
Hybrid Search
        │
        ▼
Re-ranker
        │
        ▼
GPT-5 / Claude
        │
        ▼
Medical Answer


"""