# 2026-09-26 Windows 文件锁兼容

状态：实现及 Windows 定向回归完成；真实外部链路、页面效果未验收。
关联版本：基线未知（当前目录没有可用 Git 元数据），本地修改，未提交或推送。

## 问题与计划

Windows 启动 Uvicorn 时，`json_file_stores.py` 无条件导入 Unix 专用的 `fcntl`，触发 `ModuleNotFoundError`。计划按平台选择标准库文件锁，保留跨进程互斥，无需新增依赖。

## 具体变更

- [json_file_stores.py](../../../app/infrastructure/persistence/json_file_stores.py)：Windows 使用 `msvcrt.locking` 锁定锁文件首字节，竞争时重试，其他错误上抛；退出及异常时解锁。Unix 保留 `fcntl.flock`。锁文件采用二进制模式，Windows 加解锁均定位到首字节。
- [test_preference_file_lock.py](../../../tests/test_preference_file_lock.py)：真实 spawn 子进程验证同买家互斥、不同买家独立、异常退出释放锁；使用临时目录及合成数据。
- 实现依据：[Python msvcrt 官方文档](https://docs.python.org/3/library/msvcrt.html)，字节锁允许超出文件末尾，无需写入占位内容。

## 验证与证据

原始日志目录：[windows-file-lock-20260926](../../../eval/verification/windows-file-lock-20260926/)。

1. 修复前：`.venv/Scripts/python.exe -m pytest tests/test_memory_persistence.py -q`，收集失败，复现 `No module named 'fcntl'`，见 [before.log](../../../eval/verification/windows-file-lock-20260926/before.log)。
2. 修复后：`.venv/Scripts/python.exe -m pytest tests/test_preference_file_lock.py tests/test_memory_persistence.py tests/test_buyer_workspace.py tests/test_preference_tools.py tests/test_session_fencing.py -q`，50 passed，见 [after.log](../../../eval/verification/windows-file-lock-20260926/after.log)。
3. 后端导入：`.venv/Scripts/python.exe -c "import app.presentation.server; print('server import OK')"`，成功，见 [import.log](../../../eval/verification/windows-file-lock-20260926/import.log)。此检查没有执行应用启动生命周期。

## 未完成项及启用、回滚

- 重启后端即启用；无配置变更，无业务数据迁移，不删除已有数据或锁文件。
- 回滚时恢复源文件原实现即可，但 Windows 将重新出现导入失败。
- Linux/macOS 未实机复测。真实模型、Embedding、健康接口和页面链路未验收，在线效果未知。
