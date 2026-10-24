"""Initial versioned rules and offline evidence schema."""

from alembic import op
import sqlalchemy as sa

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "rules",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(256), nullable=False),
        sa.Column("level", sa.String(20), nullable=False),
        sa.Column("logsource", sa.JSON(), nullable=False),
        sa.Column("techniques", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("current_version", sa.Integer(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_table(
        "rule_versions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("rule_id", sa.String(36), sa.ForeignKey("rules.id"), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("yaml_content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("rule_id", "version"),
    )
    op.create_table(
        "test_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("rule_id", sa.String(36), nullable=False),
        sa.Column("rule_version", sa.Integer(), nullable=False),
        sa.Column("dataset_id", sa.String(100), nullable=False),
        sa.Column("dataset_snapshot", sa.JSON(), nullable=False),
        sa.Column("report", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["rule_id", "rule_version"], ["rule_versions.rule_id", "rule_versions.version"]
        ),
    )


def downgrade():
    op.drop_table("test_runs")
    op.drop_table("rule_versions")
    op.drop_table("rules")
