import logging
from logging.config import fileConfig

from flask import current_app

from alembic import context

# Đây là đối tượng Config của Alembic, cho phép truy cập
# các giá trị trong tệp .ini đang sử dụng.
config = context.config

# Đọc tệp cấu hình ghi nhật ký của Python.
# Lệnh này thiết lập các bộ ghi nhật ký.
fileConfig(config.config_file_name)
logger = logging.getLogger('alembic.env')


def get_engine():
    try:
        # Tương thích với Flask-SQLAlchemy<3 và Alchemical
        return current_app.extensions['migrate'].db.get_engine()
    except (TypeError, AttributeError):
        # Tương thích với Flask-SQLAlchemy>=3
        return current_app.extensions['migrate'].db.engine


def get_engine_url():
    try:
        return get_engine().url.render_as_string(hide_password=False).replace(
            '%', '%%')
    except AttributeError:
        return str(get_engine().url).replace('%', '%%')


# Thêm đối tượng MetaData của mô hình tại đây
# để hỗ trợ chức năng 'autogenerate'
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
config.set_main_option('sqlalchemy.url', get_engine_url())
target_db = current_app.extensions['migrate'].db

# Các giá trị cấu hình khác, tùy theo nhu cầu của env.py,
# có thể được lấy như sau:
# my_important_option = config.get_main_option("my_important_option")
# ... và các giá trị khác.


def get_metadata():
    if hasattr(target_db, 'metadatas'):
        return target_db.metadatas[None]
    return target_db.metadata


def run_migrations_offline():
    """Chạy di chuyển cơ sở dữ liệu ở chế độ 'offline'.

    Cấu hình ngữ cảnh chỉ bằng URL, không cần đối tượng Engine,
    dù vẫn có thể sử dụng Engine tại đây. Bỏ qua bước tạo Engine
    giúp không cần có sẵn DBAPI.

    Các lệnh gọi context.execute() xuất chuỗi được cung cấp
    ra đầu ra của tập lệnh.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url, target_metadata=get_metadata(), literal_binds=True
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Chạy di chuyển cơ sở dữ liệu ở chế độ 'online'.

    Trong trường hợp này, cần tạo đối tượng Engine
    và gắn một kết nối với ngữ cảnh.

    """

    # Hàm gọi lại này ngăn việc tự động tạo bản di chuyển
    # khi lược đồ không thay đổi
    # Tham khảo: http://alembic.zzzcomputing.com/en/latest/cookbook.html
    def process_revision_directives(context, revision, directives):
        if getattr(config.cmd_opts, 'autogenerate', False):
            script = directives[0]
            if script.upgrade_ops.is_empty():
                directives[:] = []
                logger.info('No changes in schema detected.')

    conf_args = current_app.extensions['migrate'].configure_args
    if conf_args.get("process_revision_directives") is None:
        conf_args["process_revision_directives"] = process_revision_directives

    connectable = get_engine()

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=get_metadata(),
            **conf_args
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
