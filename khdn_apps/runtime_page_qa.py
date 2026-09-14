"""Open the installed production entrypoint using an isolated temporary database."""
import os
from pathlib import Path
import tempfile


def run():
    root = Path(__file__).resolve().parent
    with tempfile.TemporaryDirectory(prefix="khdn-page-qa-") as folder:
        os.environ["KHDN_DATA_DIR"] = folder
        os.environ["KHDN_DB_PATH"] = str(Path(folder) / "qa.db")
        os.environ["KHDN_REQUIRE_VOLUME"] = "0"
        from streamlit.testing.v1 import AppTest
        page = AppTest.from_file(str(root / "online_entry.py"), default_timeout=30).run()
        assert not page.exception, [e.message for e in page.exception]
        page.run()
        assert not page.exception, [e.message for e in page.exception]
        print("KHDN_RUNTIME_PAGE_QA PASS initial_open rerun isolated_database")


if __name__ == "__main__":
    run()
