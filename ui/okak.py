import requests
import datetime
import traceback
class ErrorReportDialog:
    @staticmethod
    def send_error_report(exc: Exception = None, error_text: str = None):
        error_time = datetime.datetime.now()
        try:
            if exc is not None:
                log_text = ''.join(traceback.format_exception(type(exc), exc, exc.__traceback__))
            elif error_text is not None:
                log_text = error_text
                if not log_text.strip():
                    print("Пустое сообщение об ошибке.")
                    return
            else:
                log_text = traceback.format_exc()
                if not log_text.strip() or 'NoneType: None' in log_text:
                    print("Нет данных об ошибке для отправки.")
                    return
            time_info = f"Время ошибки: {error_time.strftime('%d.%m.%Y %H:%M:%S')}"
            log_text = f"{time_info}\n\n{log_text}"
            response = requests.post(
                'https://update.smm-aviator.com/errors.php',
                data={"error": log_text},
                timeout=10,
                verify=True
            )
            if response.status_code == 200:
                print("Отчет успешно отправлен.")
            else:
                print(f"Ошибка при отправке отчета: {response.status_code} — {response.text}")
        except Exception as nested_ex:
            tb = traceback.format_exc()
            print("Ошибка при отправке отчета:\n", tb)
