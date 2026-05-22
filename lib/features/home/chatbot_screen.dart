import 'package:flutter/material.dart';
import 'package:dio/dio.dart';

class ChatbotPage extends StatefulWidget {
  const ChatbotPage({super.key});

  @override
  State<ChatbotPage> createState() => _ChatbotPageState();
}

class _ChatbotPageState extends State<ChatbotPage> {
  final TextEditingController _controller = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final List<Map<String, dynamic>> _messages = [
    {
      'message': 'مرحباً! أنا مساعدك العقاري الذكي في Findoor.\nيمكنني مساعدتك في استعراض المشاريع السكنية، الأسعار، الأقساط، وخطوات التقديم.\nكيف يمكنني مساعدتك اليوم؟',
      'isUser': false,
      'isArabic': true,
    },
  ];
  bool _isLoading = false;

  static const Color primaryBlue = Color(0xFF1E88E5);
  static const Color darkText = Color(0xFF263238);

  static const String _apiUrl = 'http://localhost:5000/api/chat';
  static const String _apiKey =
      '5b45743ddd3ded9ba2524b40cc5704b5d9839a3438a0534b4c07cfabe431eef2';

  final String _sessionId =
      'flutter_${DateTime.now().millisecondsSinceEpoch}';

  late final Dio _dio;

  @override
  void initState() {
    super.initState();
    _dio = Dio(BaseOptions(
      headers: {'X-API-Key': _apiKey, 'Content-Type': 'application/json'},
      connectTimeout: const Duration(seconds: 15),
      receiveTimeout: const Duration(seconds: 60),
    ));
  }

  @override
  void dispose() {
    _controller.dispose();
    _scrollController.dispose();
    _dio.close();
    super.dispose();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 300),
          curve: Curves.easeOut,
        );
      }
    });
  }

  bool _isArabic(String text) {
    return RegExp(r'[؀-ۿ]').hasMatch(text);
  }

  Future<void> _sendMessage() async {
    final text = _controller.text.trim();
    if (text.isEmpty || _isLoading) return;

    setState(() {
      _messages.add({
        'message': text,
        'isUser': true,
        'isArabic': _isArabic(text),
      });
      _isLoading = true;
    });
    _controller.clear();
    _scrollToBottom();

    try {
      final response = await _dio.post(
        _apiUrl,
        data: {'message': text, 'session_id': _sessionId},
      );
      final answer =
          response.data['answer'] as String? ?? 'لم أستطع الحصول على رد.';
      setState(() {
        _messages.add({
          'message': answer,
          'isUser': false,
          'isArabic': _isArabic(answer),
        });
      });
    } on DioException catch (_) {
      setState(() {
        _messages.add({
          'message':
              'عذراً، حدث خطأ في الاتصال بالخادم.\nتأكد من تشغيل الخادم على المنفذ 5000.',
          'isUser': false,
          'isArabic': true,
        });
      });
    } finally {
      setState(() => _isLoading = false);
      _scrollToBottom();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF8FAFC),
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_new, color: darkText, size: 20),
          onPressed: () => Navigator.pop(context),
        ),
        title: Row(
          children: [
            CircleAvatar(
              radius: 18,
              backgroundColor: primaryBlue.withValues(alpha: 0.1),
              child: const Icon(Icons.auto_awesome, color: primaryBlue, size: 20),
            ),
            const SizedBox(width: 12),
            const Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text("Findoor AI",
                    style: TextStyle(
                        color: darkText,
                        fontSize: 16,
                        fontWeight: FontWeight.bold)),
                Text("المساعد العقاري الذكي",
                    style: TextStyle(color: Colors.green, fontSize: 11)),
              ],
            ),
          ],
        ),
      ),
      body: Column(
        children: [
          Expanded(
            child: ListView.builder(
              controller: _scrollController,
              padding: const EdgeInsets.all(20),
              itemCount: _messages.length + (_isLoading ? 1 : 0),
              itemBuilder: (context, index) {
                if (_isLoading && index == _messages.length) {
                  return _buildTypingIndicator();
                }
                final chat = _messages[index];
                return _buildChatBubble(
                  chat['message'] as String,
                  chat['isUser'] as bool,
                  chat['isArabic'] as bool? ?? false,
                );
              },
            ),
          ),
          _buildMessageInput(),
        ],
      ),
    );
  }

  Widget _buildTypingIndicator() {
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(bottom: 16),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 14),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: const BorderRadius.only(
            topLeft: Radius.circular(20),
            topRight: Radius.circular(20),
            bottomRight: Radius.circular(20),
          ),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.03),
              blurRadius: 10,
              offset: const Offset(0, 5),
            ),
          ],
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            _dot(delay: 0),
            const SizedBox(width: 4),
            _dot(delay: 200),
            const SizedBox(width: 4),
            _dot(delay: 400),
          ],
        ),
      ),
    );
  }

  Widget _dot({required int delay}) {
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: 0.4, end: 1.0),
      duration: Duration(milliseconds: 600 + delay),
      builder: (_, v, __) => Opacity(
        opacity: v,
        child: Container(
          width: 8,
          height: 8,
          decoration: const BoxDecoration(
              color: Colors.grey, shape: BoxShape.circle),
        ),
      ),
    );
  }

  Widget _buildChatBubble(String message, bool isUser, bool isArabic) {
    final textDirection =
        isArabic ? TextDirection.rtl : TextDirection.ltr;

    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.only(bottom: 16),
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        constraints:
            BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.75),
        decoration: BoxDecoration(
          color: isUser ? primaryBlue : Colors.white,
          borderRadius: BorderRadius.only(
            topLeft: const Radius.circular(20),
            topRight: const Radius.circular(20),
            bottomLeft: Radius.circular(isUser ? 20 : 0),
            bottomRight: Radius.circular(isUser ? 0 : 20),
          ),
          boxShadow: [
            BoxShadow(
              color: Colors.black.withValues(alpha: 0.03),
              blurRadius: 10,
              offset: const Offset(0, 5),
            ),
          ],
        ),
        child: Directionality(
          textDirection: textDirection,
          child: Text(
            message,
            style: TextStyle(
              color: isUser ? Colors.white : darkText,
              fontSize: 14,
              height: 1.6,
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildMessageInput() {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 25),
      decoration: BoxDecoration(
        color: Colors.white,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 20,
            offset: const Offset(0, -5),
          ),
        ],
      ),
      child: SafeArea(
        child: Row(
          children: [
            Expanded(
              child: Container(
                padding: const EdgeInsets.symmetric(horizontal: 16),
                decoration: BoxDecoration(
                  color: const Color(0xFFF1F5F9),
                  borderRadius: BorderRadius.circular(30),
                ),
                child: TextField(
                  controller: _controller,
                  textDirection: TextDirection.rtl,
                  textAlign: TextAlign.right,
                  onSubmitted: (_) => _sendMessage(),
                  decoration: const InputDecoration(
                    hintText: "اكتب رسالتك...",
                    hintTextDirection: TextDirection.rtl,
                    border: InputBorder.none,
                    hintStyle: TextStyle(color: Colors.grey, fontSize: 14),
                  ),
                ),
              ),
            ),
            const SizedBox(width: 12),
            GestureDetector(
              onTap: _isLoading ? null : _sendMessage,
              child: CircleAvatar(
                radius: 24,
                backgroundColor:
                    _isLoading ? Colors.grey.shade300 : primaryBlue,
                child: _isLoading
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(
                            strokeWidth: 2, color: Colors.white),
                      )
                    : const Icon(Icons.send_rounded,
                        color: Colors.white, size: 20),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
