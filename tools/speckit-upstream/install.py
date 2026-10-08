#!/usr/bin/env python3
import sys
if sys.version_info < (3, 11):
    raise SystemExit('Python 3.11以上が必要です。Pythonの更新を確認してから再実行してください。')
from workbench.installer import main
if __name__ == '__main__':
    raise SystemExit(main())
