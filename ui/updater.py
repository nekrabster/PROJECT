import os
import sys
import time
import shutil
import subprocess
def wait_for_process_close(exe_name, timeout=30):
    import psutil
    start = time.time()
    while time.time() - start < timeout:
        found = False
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'] and proc.info['name'].lower() == exe_name.lower():
                    found = True
                    break
            except Exception:
                continue
        if not found:
            return True
        time.sleep(0.5)
    return False
def main():
    if len(sys.argv) < 3:
        print("Usage: updater.exe <old_exe> <new_exe>")
        sys.exit(1)
    old_exe = sys.argv[1]
    new_exe = sys.argv[2]
    if not wait_for_process_close(os.path.basename(old_exe)):
        print("Основной процесс не завершился за отведённое время.")
        sys.exit(2)
    try:
        shutil.move(new_exe, old_exe)
    except Exception as e:
        print(f"Ошибка при замене файла: {e}")
        sys.exit(3)
    try:
        subprocess.Popen([old_exe], close_fds=True)
    except Exception as e:
        print(f"Ошибка при запуске нового exe: {e}")
if __name__ == "__main__":
    main()
