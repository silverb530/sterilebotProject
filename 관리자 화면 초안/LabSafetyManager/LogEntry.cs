using System;
using System.Windows.Media;

namespace LabSafetyManager
{
    public enum LogLevel { Info, Warning, Danger }

    /// <summary>
    /// 이벤트 로그 한 항목. UI 바인딩용 표시 속성을 함께 제공한다.
    /// </summary>
    public class LogEntry
    {
        public DateTime Time { get; }
        public LogLevel Level { get; }
        public string Message { get; }

        public LogEntry(LogLevel level, string message)
        {
            Time = DateTime.Now;
            Level = level;
            Message = message;
        }

        public string TimeText => Time.ToString("HH:mm:ss");

        public Brush LevelBrush => Level switch
        {
            LogLevel.Danger => new SolidColorBrush(Color.FromRgb(0xE7, 0x4C, 0x3C)),
            LogLevel.Warning => new SolidColorBrush(Color.FromRgb(0xF1, 0xC4, 0x0F)),
            _ => new SolidColorBrush(Color.FromRgb(0x2E, 0xCC, 0x71)),
        };

        public string LevelText => Level switch
        {
            LogLevel.Danger => "위험",
            LogLevel.Warning => "주의",
            _ => "정보",
        };

        public override string ToString() =>
            $"[{Time:yyyy-MM-dd HH:mm:ss}] [{LevelText}] {Message}";
    }
}
