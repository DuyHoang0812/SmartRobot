import getpass
import sys
import warnings

from sqlalchemy.exc import SQLAlchemyError

from app.core.config import get_settings
from app.db.session import create_db_engine, create_session_factory
from app.services.bootstrap import BootstrapError, create_initial_admin


def main() -> None:
    if not sys.stdin.isatty():
        raise SystemExit("Hãy chạy CLI trong terminal tương tác để nhập mật khẩu an toàn.")
    engine = None
    try:
        username = input("Username: ")
        email = input("Email: ")
        with warnings.catch_warnings():
            # getpass otherwise falls back to echoing input on unsupported terminals.
            warnings.simplefilter("error", getpass.GetPassWarning)
            password = getpass.getpass("Mật khẩu (12–128 ký tự): ")
            confirmation = getpass.getpass("Nhập lại mật khẩu: ")
        if password != confirmation:
            raise BootstrapError("Mật khẩu nhập lại không khớp.")
        engine = create_db_engine(get_settings())
        with create_session_factory(engine)() as db:
            create_initial_admin(db, username, email, password)
        print("Đã tạo Admin đầu tiên.")
    except (BootstrapError, EOFError, KeyboardInterrupt) as error:
        raise SystemExit(str(error) or "Đã hủy.") from None
    except getpass.GetPassWarning:
        raise SystemExit(
            "Terminal không hỗ trợ nhập ẩn. Hãy dùng terminal tương tác khác."
        ) from None
    except SQLAlchemyError:
        raise SystemExit(
            "Không thể tạo Admin. Kiểm tra kết nối database và Alembic migrations."
        ) from None
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    main()
