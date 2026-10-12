"""用真实子进程验证文件锁的互斥和异常释放，不访问业务数据。"""
import multiprocessing

import pytest

from app.infrastructure.persistence.json_file_stores import JsonFilePreferenceStore


def _acquire(data_dir, buyer_id, ready, acquired):
    store = JsonFilePreferenceStore(data_dir)
    ready.set()
    with store._lock(buyer_id):
        acquired.set()


@pytest.mark.parametrize("same_buyer", [True, False])
def test_process_lock_and_exception_release(tmp_path, same_buyer):
    ctx = multiprocessing.get_context("spawn")
    ready, acquired = ctx.Event(), ctx.Event()
    store = JsonFilePreferenceStore(tmp_path)
    process = ctx.Process(
        target=_acquire,
        args=(tmp_path, "one" if same_buyer else "two", ready, acquired),
    )
    try:
        with pytest.raises(RuntimeError, match="测试异常"):
            with store._lock("one"):
                process.start()
                assert ready.wait(15), "子进程未就绪"
                if same_buyer:
                    assert not acquired.wait(0.5), "同一买家必须互斥"
                else:
                    assert acquired.wait(10), "不同买家不应互相阻塞"
                raise RuntimeError("测试异常")
        assert acquired.wait(10), "异常退出后应释放锁"
        process.join(10)
        assert process.exitcode == 0
    finally:
        if process.is_alive():
            process.terminate()
            process.join(10)
