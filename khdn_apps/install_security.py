"""Run last, after the production performance/admin source installers."""
from pathlib import Path


def main():
    app = Path(__file__).with_name('app.py')
    source = app.read_text(encoding='utf-8')
    hook = ('from khdn_apps.security_source_patch import patch_source as _security_patch_source\n'
            '_source = _security_patch_source(_source)\n')
    if hook not in source:
        marker = 'exec(compile(_source, '
        if marker not in source:
            raise RuntimeError('Cannot locate the final production source compiler')
        source = source.replace(marker, hook + marker, 1)
        app.write_text(source, encoding='utf-8')
    print('KHDN_SECURITY_SOURCE_INSTALLED session_fresh=1 password_versioned=1 raw_backup_removed=1')


if __name__ == '__main__':
    main()
