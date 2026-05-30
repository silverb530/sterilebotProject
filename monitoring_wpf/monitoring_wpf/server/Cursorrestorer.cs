using System;
using System.Runtime.InteropServices;

namespace monitoring_wpf.Services
{
    /// <summary>
    /// Learning_TWM 이 SystemParametersInfo 로 시스템 커서를 바꿔놨을 때,
    /// 강제 종료(Kill)되면 restore_cursor() 가 못 돌아서 형광초록 커서가 남는다.
    /// WPF 측에서 안전망으로 Windows API 호출해서 기본 커서로 복원.
    /// </summary>
    public static class CursorRestorer
    {
        // SystemParametersInfoW
        [DllImport("user32.dll", CharSet = CharSet.Unicode)]
        private static extern bool SystemParametersInfo(
            uint uiAction, uint uiParam, IntPtr pvParam, uint fWinIni);

        private const uint SPI_SETCURSORS = 0x0057;
        private const uint SPIF_UPDATEINIFILE = 0x01;
        private const uint SPIF_SENDCHANGE = 0x02;

        /// <summary>
        /// 시스템 기본 커서로 즉시 복원.
        /// SPI_SETCURSORS 는 Windows 의 모든 커서를 레지스트리 기준으로 리셋한다.
        /// </summary>
        public static void RestoreSystemCursors()
        {
            try
            {
                SystemParametersInfo(
                    SPI_SETCURSORS, 0, IntPtr.Zero,
                    SPIF_UPDATEINIFILE | SPIF_SENDCHANGE);
            }
            catch { /* 실패해도 무시 */ }
        }
    }
}