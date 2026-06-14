import 'package:flutter/foundation.dart' show kIsWeb;

/// Single source of truth for all backend URLs.
/// Change _lanIp to match your laptop's Wi-Fi IP (run `ipconfig` to find it).
class ApiConfig {
  static const String _lanIp = '192.168.1.8';

  /// Node.js Express — users, auth, projects, applications (port 3000)
  static String get nodeApi =>
      kIsWeb ? 'http://localhost:3000/api' : 'http://$_lanIp:3000/api';

  /// FastAPI AI backend — chatbot + OCR gateway (port 5000)
  static String get aiBase =>
      kIsWeb ? 'http://localhost:5000' : 'http://$_lanIp:5000';

  static String get chatUrl => '$aiBase/api/chat';
  static String get ocrUrl  => '$aiBase/ocr/extract';

  static const String chatApiKey =
      '5b45743ddd3ded9ba2524b40cc5704b5d9839a3438a0534b4c07cfabe431eef2';
}
