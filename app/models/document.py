"""Document metadata and sharing models."""

from extensions import db


class Document(db.Model):
    __tablename__ = "documents"

    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(512), nullable=False)
    user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    is_favorite = db.Column(
        db.Boolean, nullable=False, default=False, server_default=db.false()
    )
    is_deleted = db.Column(
        db.Boolean, nullable=False, default=False, server_default=db.false()
    )
    file_size = db.Column(db.BigInteger, nullable=False, default=0, server_default="0")
    created_at = db.Column(
        db.DateTime, nullable=False, server_default=db.func.current_timestamp()
    )

    owner = db.relationship("User", back_populates="documents", lazy="joined")
    shares = db.relationship(
        "DocumentShare",
        back_populates="document",
        cascade="all, delete-orphan",
        lazy="select",
    )

    def to_dict(self, include_owner=False):
        data = {
            "id": self.id,
            "filename": self.filename,
            "file_size": self.file_size,
            "created_at": self.created_at,
            "is_favorite": bool(self.is_favorite),
            "is_deleted": bool(self.is_deleted),
        }
        if include_owner:
            data["owner_id"] = self.user_id
            data["owner_name"] = self.owner.username if self.owner else None
        return data


class DocumentShare(db.Model):
    __tablename__ = "document_shares"
    __table_args__ = (
        db.UniqueConstraint(
            "document_id", "shared_with_user_id", name="uq_document_share_recipient"
        ),
    )

    id = db.Column(db.Integer, primary_key=True)
    document_id = db.Column(
        db.Integer,
        db.ForeignKey("documents.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    shared_with_user_id = db.Column(
        db.Integer,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    document = db.relationship("Document", back_populates="shares")
    recipient = db.relationship("User", back_populates="received_shares")
