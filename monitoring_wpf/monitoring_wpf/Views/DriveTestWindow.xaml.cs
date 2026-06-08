using System;
using System.Net.Http;
using System.Text.Json;
using System.Threading.Tasks;
using System.Windows;
using System.Windows.Threading;

namespace monitoring_wpf.Views
{
    public partial class DriveTestWindow : Window
    {
        private static readonly HttpClient _http = new() { Timeout = TimeSpan.FromSeconds(10) };
        private const string PiBase = "http://192.168.0.32:5001";

        private static readonly string[] Slots =
            { "A1", "A2", "A3", "A4", "B1", "B2", "B3", "B4" };

        public DriveTestWindow()
        {
            InitializeComponent();
            Loaded += async (_, _) => await RunTestAsync();
        }

        private async Task RunTestAsync()
        {
            // 랜덤 2개 선택
            var rng = new Random();
            int i1 = rng.Next(Slots.Length);
            int i2;
            do { i2 = rng.Next(Slots.Length); } while (i2 == i1);

            string[] targets = { Slots[i1], Slots[i2] };

            for (int step = 0; step < targets.Length; step++)
            {
                string slot = targets[step];

                // 상태 표시
                SetStatus($"({step + 1}/2) 이동 중...", slot, $"목표 슬롯: {slot}");

                // Pi에 이동 명령
                bool ok = await SendCommandAsync($"/drop_move/{slot}");
                if (!ok)
                {
                    SetStatus("오류", "통신 실패", "Pi 서버 연결을 확인하세요.");
                    return;
                }

                // busy=false 될 때까지 폴링
                await WaitUntilIdleAsync();

                // 홈 복귀
                SetStatus($"({step + 1}/2) 홈 복귀 중...", slot, "영점으로 돌아가는 중");
                await SendCommandAsync("/home");
                await WaitUntilIdleAsync();
            }

            // 완료
            SetStatus("완료", "✓", "구동 테스트가 완료되었습니다");
            TitleText.Text = "구동 테스트 완료";

            // 3초 후 닫기
            await Task.Delay(3000);
            Dispatcher.Invoke(Close);
        }

        private async Task<bool> SendCommandAsync(string path)
        {
            try
            {
                var res = await _http.GetAsync($"{PiBase}{path}");
                var json = await res.Content.ReadAsStringAsync();
                var doc = JsonDocument.Parse(json);
                return doc.RootElement.GetProperty("ok").GetBoolean();
            }
            catch (Exception ex)
            {
                System.Diagnostics.Debug.WriteLine($"[DriveTest] 명령 실패 {path}: {ex.Message}");
                return false;
            }
        }

        private async Task WaitUntilIdleAsync()
        {
            for (int i = 0; i < 120; i++)   // 최대 60초 대기
            {
                await Task.Delay(500);
                try
                {
                    var res = await _http.GetAsync($"{PiBase}/status");
                    var json = await res.Content.ReadAsStringAsync();
                    var doc = JsonDocument.Parse(json);
                    bool busy = doc.RootElement.GetProperty("busy").GetBoolean();
                    if (!busy) return;
                }
                catch
                {
                    // 네트워크 일시 오류 → 계속 폴링
                }
            }
        }

        private void SetStatus(string step, string slot, string count)
        {
            Dispatcher.Invoke(() =>
            {
                StepText.Text = step;
                SlotText.Text  = slot;
                CountText.Text = count;
            });
        }
    }
}
