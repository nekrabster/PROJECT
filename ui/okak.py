import os
import base64
import certifi
import requests
import datetime
class ErrorReportDialog:
    @staticmethod
    def send_error_report(log_path, error_time=None, error_text=None):
        error_time = error_time or datetime.datetime.now()
        try:
            if error_text:
                log_text = error_text
            else:
                if not log_path or not os.path.exists(log_path):
                    log_text = 'Ошибка: неизвестная ошибка.'
                else:
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
            if not log_text.strip():
                print("Нет данных для отправки.")
                return
            time_info = f"Время возникновения ошибки: {error_time.strftime('%d.%m.%Y %H:%M:%S')}"
            log_text = f"{time_info}\n\n{log_text}"

            kwargs = {"data": {"error": log_text}}
            try:
                kwargs["verify"] = certifi.where()
            except Exception:
                pass
            response = requests.post('https://update.smm-aviator.com/errors.php', **kwargs)
            if response.status_code == 200:
                print("Отчет успешно отправлен.")
            else:
                print("Не удалось отправить отчет. Попробуйте позже.")

        except Exception as ex:
            print("Не удалось отправить отчет. Попробуйте позже.")
