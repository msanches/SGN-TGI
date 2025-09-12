# Sistema Acadêmico TGI — Skeleton (Flask + MySQL)

Esqueleto com autenticação, RBAC (admin/professor/convidado), telas iniciais de Admin (Alunos e criação de Grupos) e configuração por `DATABASE_URL` ou variáveis `DB_*` (auto-build).

## Stack
- Flask + Jinja2 templates
- SQLAlchemy + Flask-Migrate
- Flask-Login, Flask-WTF, Flask-Bcrypt, python-dotenv
- MySQL (via `mysql+pymysql`) com fallback SQLite (dev)
- openpyxl (export Excel — demo)

## Como rodar

1) Crie o venv e instale:
```bash
python -m venv .venv
# Windows (CMD): .venv\Scripts\activate
# PowerShell:    .venv\Scripts\Activate.ps1
# Linux/macOS:   source .venv/bin/activate
pip install -r requirements.txt
```

2) Crie `.env` (base em `.env.example`). Use **uma** opção:

### Opção A) URL completa (prioritária)
```
DATABASE_URL=mysql+pymysql://tgi:SUA_SENHA@127.0.0.1:3306/tgi_db?charset=utf8mb4
```

### Opção B) Variáveis separadas (o app monta a URL com percent-encoding)
```
DB_DIALECT=mysql
DB_DRIVER=pymysql
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=tgi_db
DB_USER=tgi
DB_PASS=sua_senha#com@caracteres:especiais
```

3) Migrações:
```bash
flask db init
flask db migrate -m "initial"
flask db upgrade
```

4) Crie um admin:
```bash
flask create-user --email admin@tgi.edu --password 123456 --name "Admin" --role admin
```

5) Rode:
```bash
flask run
```
Acesse: http://127.0.0.1:5000/login

## Rotas úteis
- `/admin/` — dashboard admin (+ atalhos para Alunos e Criar Grupo)
- `/admin/students` — listar alunos
- `/admin/students/new` — novo aluno
- `/admin/groups/new` — criar grupo por RGMs
- `/admin/export/excel` — export demo xlsx

## Observações
- Tabela de grupos usa nome **tgi_groups** (evita conflito com palavra reservada).
- Se ver “Forbidden”, garanta que o usuário tem `role=admin`. No shell:
```python
from app.models import User, Role
from app.extensions import db
u = User.query.filter_by(email="admin@tgi.edu").first()
u.role = Role.admin
db.session.commit()
```
