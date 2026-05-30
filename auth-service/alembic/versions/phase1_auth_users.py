"""
Esse arquivo é resposável pela criação do enum de papéis de usuário e pela tabela users para autenticação 
e controle de acesso.
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "phase1_auth_users"
down_revision = "phase0_base"
branch_labels = None
depends_on = None


def upgrade() -> None:
    """ 
    Aplica a migração para criar a tabela de usuários com as informações de autenticação e 
    controle de acesso.
    Também cria o enum user_role para definir os papéis de usuário, além de 
    índice que garante a unicidade do email.
    args:
        None
    returns:
        None
    """
    user_role_enum = sa.Enum(
        "USER", 
        "ADMIN", 
        name="user_role", 
        native_enum=False,
    )
    user_role_enum.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "users",
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "role", 
            user_role_enum, 
            nullable=False, 
            server_default="USER"
        ),
        sa.Column(
            "is_active", 
            sa.Boolean(), 
            nullable=False, 
            server_default=sa.true()
        ),
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

def downgrade() -> None:
    """
    Reverte as mudanças feitas no upgrade, removendo a tabela de usuários e o enum de papéis de usuário.
    A ordem é importante para evitar conflitos.
    args:
        None
    returns:
        None
    """
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
    user_role_enum = sa.Enum("USER", "ADMIN", name="user_role", native_enum=False)
    user_role_enum.drop(op.get_bind(), checkfirst=True)
