// 비상상황 판단용
unsigned long gasHighStart = 0;       // 400이상 청므 감지된 시간 (ms)
bool emergencySent = false;             // 현재 경고 상태인지 여부


// 팬 핀
const int FAN_PIN = 4;

// 종료 후 환기용 변수
bool venting = false;                  // 환기 중인지 여부
unsigned long ventStart = 0;           // 환기 시작 시각
unsigned long ventDuration = 180000;   // 환기 시간 (기본 3분 = 180000ms)
unsigned long gasLowStart = 0;         // 가스 260 미만 연속 시작 시각

// 가장먼저 실행되는 초기화 함수
void setup() {
  Serial.begin(9600);             // PC 시리얼 모니터 통신속도
  Serial.setTimeout(50);

  pinMode(FAN_PIN, OUTPUT);                // 팬 핀 출력 설정
  digitalWrite(FAN_PIN, LOW);              // 시작 시 팬 OFF
}


// main문 역할
void loop() {
  checkCommand();

  if (venting) {           // 환기 중이면 환기 로직
    handleVenting();
  } else {
    readGas();
  }         
}


// WPF -> PI -> 아두이노 (종료시)
void checkCommand(){
  if(Serial.available()){
    String cmd = Serial.readStringUntil('\n');
    cmd.trim();
    Serial.println("받은명령:[" + cmd + "]");
    // WPF에서 보내는 환기 신호
    if(cmd == "VENT_START"){
      venting = true;
      ventStart = millis();
      ventDuration = 10000;
      gasLowStart = 0;
      digitalWrite(FAN_PIN, HIGH);
      Serial.println("환기 시작");
    }
    else if(cmd == "FAN_ON"){           // ◀ 추가: 비상 시 팬 켜기
      digitalWrite(FAN_PIN, HIGH);
      Serial.println("팬 ON");
    }
    else if(cmd == "FAN_OFF"){          // ◀ 추가: 비상 해제 시 팬 끄기
      digitalWrite(FAN_PIN, LOW);
      venting = false;
      Serial.println("팬 OFF");
    }
  }
}

// 환기
void handleVenting(){
  int gasValue = analogRead(A0);

  // 1초마다 현재 가스값 전송 (WPF 알림창 표시용)
  static unsigned long lastGas = 0;
  if(millis() - lastGas >= 1000) {
    Serial.println("VENT_GAS:" + String(gasValue));
    lastGas = millis();
  }

  // 가스 260미만일경우 1분씩 계속 틈
  if(gasValue < 260){
    if (gasLowStart == 0) gasLowStart = millis();
  }else{
    gasLowStart = 0;
  }

  // 설정 시간 경과 시 종료 조건 확인
  if(millis() - ventStart >= ventDuration){
    // 가스가 3초 이상 연속 260미만 유지 됐는지 확인
    if(gasLowStart != 0 && millis() - gasLowStart >= 3000){
      digitalWrite(FAN_PIN, LOW);   // 팬끔
      Serial.println("VENT_DONE");  // 환풍 완료 - pi전달
      venting = false;
    }
    else{
      ventDuration += 60000;
    }
  }
  delay(100);
}

// 가스센서 가스농도 값 읽기
void readGas(){
  // A0 핀에서 아날로그 값 읽기 (0~1023)
  int gasValue = analogRead(A0);

  // 1초마다 가스값 전송
  static unsigned long lastGasSend = 0;
  if(millis() - lastGasSend >= 1000){
    Serial.println("GAS:" + String(gasValue));
    lastGasSend = millis();
  }

  //Serial.print("현재 가스 농도 ： ");
  //Serial.println(gasValue);
  // 400이상 가스농도 , 3초이상 누출 시 이요이용
  if(gasValue >= 400){
    digitalWrite(FAN_PIN, HIGH);      // 팬 on

    if(gasHighStart == 0){          // 처음 400넘는 순간 시간 시작
      gasHighStart = millis();      // 경과시간 (ms)
    }
    
    // 3초 지속 시 전송
    if(!emergencySent && millis() - gasHighStart >= 3000){        // 비상코드가 FALSE면서 3초 이상이면 비상신호 라파에 전달

      sendEmergency(gasValue);    // 라파전달
      emergencySent = true;
    }
  }
  // 비상상황 종료 또는 아닐경우
  else {
    digitalWrite(FAN_PIN,LOW);    // 팬 off
    if (emergencySent) {
        Serial.println("EMERGENCY_END");  // ← 추가
    }
    emergencySent = false;        // 리셋
    gasHighStart = 0;             // 리셋
  }
  delay(100);
}


// 비상상황 라파에 전달
void sendEmergency(int gasValue){
  Serial.println("EMERGENCY:" + String(gasValue));  // 가스값 포함해서 Pi로 전송
  Serial.println("비상신호 전송완료");
}

