import time


class RefreshTimerFormatter:
    def format_last_refresh_message(self, last_refresh_timestamp):
        if last_refresh_timestamp is None:
            return "Последнее обновление: ещё не выполнялось"

        elapsed_seconds = max(0, int(time.time() - last_refresh_timestamp))
        hours, remainder = divmod(elapsed_seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        return f"Последнее обновление: {hours:02}:{minutes:02}:{seconds:02} назад"
