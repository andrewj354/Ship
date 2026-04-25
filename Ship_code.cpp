#include <WiFi.h>
#include <WebServer.h>
#include <OneWire.h>
#include <DallasTemperature.h>
#include <TinyGPS++.h>
#include <ESP32Servo.h>

// --- ПІНИ ---
const int ONE_WIRE_BUS = 4;
const int RXD2 = 16;
const int TXD2 = 17;
const int RELAY_PIN = 25;
const int SERVO_PIN = 26;
const int PH_PIN = 34;
const int TURB_PIN = 35;

// --- НАЛАШТУВАННЯ WI-FI (Точка доступу) ---
const char *ssid = "WaterDrone";
const char *password = "12345678";
WebServer server(80);

// --- ОБ'ЄКТИ ДЛЯ ДАТЧИКІВ ТА МОТОРІВ ---
OneWire oneWire(ONE_WIRE_BUS);
DallasTemperature sensors(&oneWire);
HardwareSerial GPS_Serial(2); // Використовуємо апаратний Serial2
TinyGPSPlus gps;
Servo myServo;

// Змінні для збереження даних
float tempC = 0.0;
float phVoltage = 0.0;
float turbVoltage = 0.0;
float phValue = 0.0;
String gpsLat = "Шукаю супутники...";
String gpsLng = "Шукаю супутники...";

void setup() {
  Serial.begin(115200);
  
  // Налаштування пінів
  pinMode(RELAY_PIN, OUTPUT);
  digitalWrite(RELAY_PIN, LOW); // Мотор вимкнено за замовчуванням
  
  myServo.attach(SERVO_PIN);
  myServo.write(90); // Ставимо серво по центру
  
  // Запуск датчиків
  sensors.begin();
  GPS_Serial.begin(9600, SERIAL_8N1, RXD2, TXD2);
  
  // Налаштування Wi-Fi
  Serial.println("Створення Wi-Fi точки доступу...");
  WiFi.softAP(ssid, password);
  IPAddress IP = WiFi.softAPIP();
  Serial.print("IP адреса дрона: ");
  Serial.println(IP);

  // Налаштування веб-сторінок
  server.on("/", handleRoot);
  server.on("/motor_on", []() { digitalWrite(RELAY_PIN, HIGH); handleRoot(); });
  server.on("/motor_off", []() { digitalWrite(RELAY_PIN, LOW); handleRoot(); });
  server.on("/servo_left", []() { myServo.write(45); handleRoot(); });
  server.on("/servo_center", []() { myServo.write(90); handleRoot(); });
  server.on("/servo_right", []() { myServo.write(135); handleRoot(); });

  server.begin();
}

void loop() {
  server.handleClient(); // Обслуговування веб-сервера
  
  // Читання GPS
  while (GPS_Serial.available() > 0) {
    gps.encode(GPS_Serial.read());
  }
  if (gps.location.isUpdated()) {
    gpsLat = String(gps.location.lat(), 6);
    gpsLng = String(gps.location.lng(), 6);
  }

  // Зчитування інших датчиків (раз на секунду для плавності)
  static unsigned long lastUpdate = 0;
  if (millis() - lastUpdate > 1000) {
    lastUpdate = millis();
    
    // Температура
    sensors.requestTemperatures(); 
    tempC = sensors.getTempCByIndex(0);
    
    // pH та Мутність (ESP32 ADC видає 0-4095 для 0-3.3V)
    // Формула: (Значення / 4095.0) * 3.3V * 1.5 (Коефіцієнт дільника напруги 10k/20k)
    phVoltage = (analogRead(PH_PIN) / 4095.0) * 3.3 * 1.5;
    turbVoltage = (analogRead(TURB_PIN) / 4095.0) * 3.3 * 1.5;
    
    // Приблизний перерахунок pH (потребує калібрування!)
    phValue = 7.00 + ((2.5 - phVoltage) * 3.5); 
  }
}

// --- ФУНКЦІЯ ГЕНЕРАЦІЇ ВЕБ-СТОРІНКИ ---
void handleRoot() {
  String html = "<!DOCTYPE html><html><head><meta charset='UTF-8'>";
  html += "<meta name='viewport' content='width=device-width, initial-scale=1.0'>";
  html += "<title>Water Drone Control</title>";
  html += "<style>body{font-family: Arial; text-align: center; margin: 20px;} ";
  html += "h1{color: #007BFF;} .btn{display: inline-block; padding: 15px 25px; ";
  html += "font-size: 18px; margin: 10px; color: white; background-color: #28A745; ";
  html += "text-decoration: none; border-radius: 5px;} .btn-red{background-color: #DC3545;} ";
  html += ".btn-blue{background-color: #007BFF;} .data-box{border: 1px solid #ccc; ";
  html += "padding: 15px; margin: 20px auto; width: 90%; max-width: 400px; border-radius: 10px;} ";
  html += "</style></head><body>";
  
  html += "<h1>🌊 Панель керування дроном</h1>";
  
  html += "<div class='data-box'>";
  html += "<h3>Показники датчиків:</h3>";
  html += "<p><b>Температура:</b> " + String(tempC) + " °C</p>";
  html += "<p><b>pH води:</b> " + String(phValue, 2) + " (Напруга: " + String(phVoltage, 2) + "V)</p>";
  html += "<p><b>Мутність:</b> " + String(turbVoltage, 2) + " V (Чим більше, тим чистіше)</p>";
  html += "<p><b>GPS:</b> " + gpsLat + ", " + gpsLng + "</p>";
  html += "<a href='/' class='btn btn-blue'>🔄 Оновити дані</a>";
  html += "</div>";

  html += "<div class='data-box'>";
  html += "<h3>Ходовий мотор:</h3>";
  html += "<a href='/motor_on' class='btn'>🟢 УВІМКНУТИ</a>";
  html += "<a href='/motor_off' class='btn btn-red'>🔴 ВИМКНУТИ</a>";
  html += "</div>";

  html += "<div class='data-box'>";
  html += "<h3>Кермо (Серво):</h3>";
  html += "<a href='/servo_left' class='btn btn-blue'>Вліво</a>";
  html += "<a href='/servo_center' class='btn btn-blue'>Прямо</a>";
  html += "<a href='/servo_right' class='btn btn-blue'>Вправо</a>";
  html += "</div>";

  html += "</body></html>";
  
  server.send(200, "text/html", html);
}