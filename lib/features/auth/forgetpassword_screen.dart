import 'package:flutter/material.dart';

class ForgotPasswordScreen extends StatefulWidget {
  const ForgotPasswordScreen({super.key});

  @override
  State<ForgotPasswordScreen> createState() => _ForgotPasswordScreenState();
}

class _ForgotPasswordScreenState extends State<ForgotPasswordScreen> {
  String selectedMethod = 'email';
  final TextEditingController _inputController = TextEditingController();

  void _handleReset() {
    String methodText = selectedMethod == 'email' ? "Email" : "SMS";

    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(
        content: Text("Reset code sent via $methodText successfully!"),
        backgroundColor: Colors.green,
        behavior: SnackBarBehavior.floating,
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_new, color: Colors.black, size: 20),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.symmetric(horizontal: 30),
        child: Column(
          children: [
            const SizedBox(height: 10),
            // Security Icon Header
            _buildAnimatedHeader(),

            const SizedBox(height: 30),
            const Text(
              "Recovery Method",
              style: TextStyle(fontSize: 26, fontWeight: FontWeight.bold, color: Color(0xFF263238)),
            ),
            const SizedBox(height: 10),
            const Text(
              "How would you like to receive the reset code?",
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 15, color: Colors.grey),
            ),

            const SizedBox(height: 35),

            // كروت الاختيار (Email vs Phone)
            _buildSelectionCard(
              id: 'email',
              title: "Via Email Address",
              subtitle: "Send to your registered Gmail",
              icon: Icons.alternate_email_rounded,
            ),
            const SizedBox(height: 15),
            _buildSelectionCard(
              id: 'phone',
              title: "Via Phone Number",
              subtitle: "Send as SMS to your mobile",
              icon: Icons.sms_outlined,
            ),

            const SizedBox(height: 40),

            // حقل الإدخال الديناميكي
            _buildDynamicField(),

            const SizedBox(height: 40),

            // زر الإرسال
            _buildSendButton(),
          ],
        ),
      ),
    );
  }

  // Header مع دايرة خلفية أنيقة
  Widget _buildAnimatedHeader() {
    return Container(
      padding: const EdgeInsets.all(25),
      decoration: BoxDecoration(
        color: const Color(0xFF1E88E5).withValues(alpha: 0.1),
        shape: BoxShape.circle,
      ),
      child: const Icon(Icons.vpn_lock_rounded, size: 70, color: Color(0xFF1E88E5)),
    );
  }

  Widget _buildSelectionCard({required String id, required String title, required String subtitle, required IconData icon}) {
    bool isSelected = selectedMethod == id;

    return GestureDetector(
      onTap: () => setState(() => selectedMethod = id),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 300),
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: isSelected ? const Color(0xFF1E88E5).withValues(alpha: 0.05) : Colors.white,
          borderRadius: BorderRadius.circular(15),
          border: Border.all(
            color: isSelected ? const Color(0xFF1E88E5) : Colors.grey.shade200,
            width: isSelected ? 2 : 1,
          ),
        ),
        child: Row(
          children: [
            Icon(icon, color: isSelected ? const Color(0xFF1E88E5) : Colors.grey, size: 28),
            const SizedBox(width: 15),
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(title, style: TextStyle(fontWeight: FontWeight.bold, fontSize: 16, color: isSelected ? const Color(0xFF1E88E5) : Colors.black87)),
                Text(subtitle, style: const TextStyle(fontSize: 13, color: Colors.grey)),
              ],
            ),
            const Spacer(),
            if (isSelected) const Icon(Icons.check_circle, color: Color(0xFF1E88E5)),
          ],
        ),
      ),
    );
  }

  // الحقل اللي بيتغير بناءً على الاختيار
  Widget _buildDynamicField() {
    return TextField(
      controller: _inputController,
      keyboardType: selectedMethod == 'email' ? TextInputType.emailAddress : TextInputType.phone,
      decoration: InputDecoration(
        labelText: selectedMethod == 'email' ? "Email Address" : "Phone Number",
        hintText: selectedMethod == 'email' ? "example@gmail.com" : "01xxxxxxxxx",
        prefixIcon: Icon(selectedMethod == 'email' ? Icons.email_outlined : Icons.phone_iphone_rounded, color: const Color(0xFF1E88E5)),
        filled: true,
        fillColor: const Color(0xFFF8FAFC),
        enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(15), borderSide: BorderSide(color: Colors.grey.shade200)),
        focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(15), borderSide: const BorderSide(color: Color(0xFF1E88E5), width: 2)),
      ),
    );
  }

  // زر الإرسال الاحترافي مع Shadow
  Widget _buildSendButton() {
    return Container(
      width: double.infinity,
      height: 55,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(15),
        boxShadow: [
          BoxShadow(color: const Color(0xFF1E88E5).withValues(alpha: 0.3), blurRadius: 10, offset: const Offset(0, 5))
        ],
      ),
      child: ElevatedButton(
        onPressed: _handleReset,
        style: ElevatedButton.styleFrom(
          backgroundColor: const Color(0xFF1E88E5),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(15)),
          elevation: 0,
        ),
        child: const Text("SEND RECOVERY CODE", style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, letterSpacing: 1)),
      ),
    );
  }
}