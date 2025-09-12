import os
from urllib.parse import quote_plus
from dotenv import load_dotenv, find_dotenv

# Procura o .env a partir da raiz do projeto
load_dotenv(find_dotenv())

def _build_mysql_uri_from_env():
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT", "3306")
    name = os.getenv("DB_NAME")
    user = os.getenv("DB_USER")
    pwd  = os.getenv("DB_PASS")
    dialect = os.getenv("DB_DIALECT", "mysql")
    driver  = os.getenv("DB_DRIVER", "pymysql")

    if not all([host, name, user, pwd]):
        return None

    user_enc = quote_plus(user)
    pwd_enc  = quote_plus(pwd)
    return f"{dialect}+{driver}://{user_enc}:{pwd_enc}@{host}:{port}/{name}?charset=utf8mb4"

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "devkey-change-me")

    _explicit_url = os.getenv("DATABASE_URL")
    _built_url = _build_mysql_uri_from_env()

    if _explicit_url:
        SQLALCHEMY_DATABASE_URI = _explicit_url
    elif _built_url:
        SQLALCHEMY_DATABASE_URI = _built_url
    else:
        inst_dir = os.path.join(os.getcwd(), "instance")
        os.makedirs(inst_dir, exist_ok=True)
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{os.path.join(inst_dir, 'app.db')}"

    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SESSION_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_HTTPONLY = True
    WTF_CSRF_ENABLED = True

    # Log SQL (opcional para debug): defina SQLALCHEMY_ECHO=1 no .env
    SQLALCHEMY_ECHO = os.getenv("SQLALCHEMY_ECHO") == "1"
