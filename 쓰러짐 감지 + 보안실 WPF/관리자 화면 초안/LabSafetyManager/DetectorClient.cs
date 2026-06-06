using System;
using System.Net.WebSockets;
using System.Text;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;

namespace LabSafetyManager
{
    public class StateChangedEventArgs : EventArgs
    {
        public string State { get; init; } = "normal";
        public string Timestamp { get; init; } = "";
    }

    /// <summary>
    /// Python 감지기(WebSocket 서버)에 접속해 영상 프레임과 상태 이벤트를 받는다.
    /// 연결이 끊기면 2초마다 자동으로 재연결한다. 외부 패키지 없이 .NET 내장 기능만 사용.
    /// </summary>
    public class DetectorClient
    {
        private readonly Uri _uri;
        private CancellationTokenSource? _cts;

        public event EventHandler<byte[]>? FrameReceived;
        public event EventHandler<StateChangedEventArgs>? StateChanged;
        public event EventHandler<bool>? ConnectionChanged;

        public DetectorClient(string url = "ws://127.0.0.1:8765")
        {
            _uri = new Uri(url);
        }

        public void Start()
        {
            _cts = new CancellationTokenSource();
            _ = Task.Run(() => RunLoopAsync(_cts.Token));
        }

        public void Stop()
        {
            _cts?.Cancel();
        }

        private async Task RunLoopAsync(CancellationToken token)
        {
            while (!token.IsCancellationRequested)
            {
                using var ws = new ClientWebSocket();
                try
                {
                    await ws.ConnectAsync(_uri, token);
                    ConnectionChanged?.Invoke(this, true);
                    await ReceiveAsync(ws, token);
                }
                catch (OperationCanceledException)
                {
                    break;
                }
                catch
                {
                    // 연결 실패/끊김 -> 아래에서 잠시 후 재시도
                }

                if (token.IsCancellationRequested) break;
                ConnectionChanged?.Invoke(this, false);

                try { await Task.Delay(2000, token); }
                catch (OperationCanceledException) { break; }
            }
        }

        private async Task ReceiveAsync(ClientWebSocket ws, CancellationToken token)
        {
            var buffer = new byte[64 * 1024];
            var sb = new StringBuilder();

            while (ws.State == WebSocketState.Open && !token.IsCancellationRequested)
            {
                sb.Clear();
                WebSocketReceiveResult result;
                do
                {
                    result = await ws.ReceiveAsync(new ArraySegment<byte>(buffer), token);
                    if (result.MessageType == WebSocketMessageType.Close)
                    {
                        await ws.CloseAsync(WebSocketCloseStatus.NormalClosure, "", token);
                        return;
                    }
                    sb.Append(Encoding.UTF8.GetString(buffer, 0, result.Count));
                }
                while (!result.EndOfMessage);

                HandleMessage(sb.ToString());
            }
        }

        private void HandleMessage(string json)
        {
            try
            {
                using var doc = JsonDocument.Parse(json);
                var root = doc.RootElement;
                if (!root.TryGetProperty("type", out var typeEl)) return;
                var type = typeEl.GetString();

                if (type == "frame")
                {
                    var b64 = root.GetProperty("jpg").GetString();
                    if (!string.IsNullOrEmpty(b64))
                    {
                        var bytes = Convert.FromBase64String(b64);
                        FrameReceived?.Invoke(this, bytes);
                    }
                }
                else if (type == "state")
                {
                    var state = root.GetProperty("value").GetString() ?? "normal";
                    var ts = root.TryGetProperty("ts", out var tsEl)
                        ? tsEl.GetString() ?? ""
                        : "";
                    StateChanged?.Invoke(this,
                        new StateChangedEventArgs { State = state, Timestamp = ts });
                }
            }
            catch
            {
                // 깨진 메시지는 무시
            }
        }
    }
}
