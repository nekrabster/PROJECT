import os
import base64
import requests
import datetime
import traceback
class ErrorReportDialog:
    @staticmethod
    def send_error_report(log_path=None, error_time=None, error_text=None):
        error_time = error_time or datetime.datetime.now()
        try:
            log_text = ""
            if error_text:
                log_text = error_text
            elif log_path and os.path.exists(log_path):
                with open(log_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                decrypted_lines = []
                for line in lines:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        decrypted = base64.b64decode(line.encode('utf-8')).decode('utf-8')
                        decrypted_lines.append(decrypted)
                    except Exception:
                        decrypted_lines.append(line)
                log_text = '\n'.join(decrypted_lines[-50:]) if decrypted_lines else ''
            else:
                log_text = 'Ошибка: лог-файл не найден или пуст.'
            if not log_text.strip():
                print("Нет данных для отправки.")
                return
            time_info = f"Время ошибки: {error_time.strftime('%d.%m.%Y %H:%M:%S')}"
            log_text = f"{time_info}\n\n{log_text}"
            response = requests.post(
                'https://update.smm-aviator.com/errors.php',
                data={"error": log_text},
                verify=True
            )
            if response.status_code == 200:
                print("Отчет успешно отправлен.")
            else:
                print(f"Ошибка при отправке отчета: {response.status_code} — {response.text}")
        except Exception as ex:
            tb = traceback.format_exc()
            print("Исключение при отправке отчета:\n", tb)
            try:
                error_time = datetime.datetime.now()
                log_text = f"Время ошибки (внутреннее исключение): {error_time.strftime('%d.%m.%Y %H:%M:%S')}\n\n{tb}"
                requests.post(
                    'https://update.smm-aviator.com/errors.php',
                    data={"error": log_text},
                    verify=True
                )
            except Exception as nested_ex:
                print("Ошибка при повторной отправке traceback:", nested_ex)
