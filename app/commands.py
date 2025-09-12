import click
from .extensions import db
from .models import User, Role

def register_commands(app):
    @app.cli.command("create-user")
    @click.option("--email", prompt=True)
    @click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
    @click.option("--name", prompt=True)
    @click.option("--role", prompt=True, type=click.Choice([r.value for r in Role]))
    def create_user(email, password, name, role):
        """Cria um usuário novo."""
        if User.query.filter_by(email=email).first():
            click.echo("Usuário já existe.")
            return
        u = User(email=email, full_name=name, role=Role(role))
        u.set_password(password)
        db.session.add(u)
        db.session.commit()
        click.echo(f"Usuário {email} criado com sucesso.")
