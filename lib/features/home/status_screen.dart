import 'package:flutter/material.dart';

enum AppStatus { submitted, pending, approved, rejected }

class StatusPage extends StatelessWidget {
  // القيمة دي هي اللي هتتغير لما نربط مع الـ Node.js
  final AppStatus currentStatus = AppStatus.rejected;

  const StatusPage({super.key});

  static const Color darkText = Color(0xFF263238);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF8FAFC),
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0.5,
        centerTitle: true,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_new, color: darkText, size: 20),
          onPressed: () => Navigator.pop(context),
        ),
        title: const Text("Application Status",
            style: TextStyle(color: darkText, fontWeight: FontWeight.bold, fontSize: 18)),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          children: [
            _buildDynamicStatusCard(),
            const SizedBox(height: 32),
            _buildStatusDescription(),
            const SizedBox(height: 40),
            _buildActionButtons(context),
          ],
        ),
      ),
    );
  }

  Widget _buildDynamicStatusCard() {
    Color bgColor;
    IconData icon;
    String label;

    // تحديد اللون بناءً على الحالة المطلوبة
    switch (currentStatus) {
      case AppStatus.submitted:
        bgColor = Colors.blue.shade600;
        icon = Icons.send_rounded;
        label = "Submitted";
        break;
      case AppStatus.pending:
        bgColor = Colors.orange.shade600;
        icon = Icons.hourglass_empty_rounded;
        label = "Pending Review";
        break;
      case AppStatus.approved:
        bgColor = Colors.green.shade600;
        icon = Icons.check_circle_rounded;
        label = "Approved";
        break;
      case AppStatus.rejected:
        bgColor = Colors.red.shade600;
        icon = Icons.cancel_rounded;
        label = "Rejected";
        break;
    }

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(vertical: 40, horizontal: 20),
      decoration: BoxDecoration(
        color: bgColor, // تغيير خلفية الكارت بالكامل
        borderRadius: BorderRadius.circular(28),
        boxShadow: [
          BoxShadow(
            color: bgColor.withValues(alpha: 0.3),
            blurRadius: 15,
            offset: const Offset(0, 8),
          )
        ],
      ),
      child: Column(
        children: [
          Icon(icon, color: Colors.white, size: 70),
          const SizedBox(height: 16),
          Text(
            label,
            style: const TextStyle(
              fontSize: 26,
              fontWeight: FontWeight.bold,
              color: Colors.white,
              letterSpacing: 1,
            ),
          ),
          const SizedBox(height: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.2),
              borderRadius: BorderRadius.circular(10),
            ),
            child: const Text(
              "ID: #APP-99201",
              style: TextStyle(color: Colors.white, fontSize: 13, fontWeight: FontWeight.w500),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildStatusDescription() {
    String title;
    String sub;

    switch (currentStatus) {
      case AppStatus.submitted:
        title = "Application Received";
        sub = "We have successfully received your request and it's now in our system.";
        break;
      case AppStatus.pending:
        title = "Under Official Review";
        sub = "A government officer is currently verifying your documents and eligibility.";
        break;
      case AppStatus.approved:
        title = "Ready for Contract";
        sub = "Great news! Your application was accepted. Please proceed to the next step.";
        break;
      case AppStatus.rejected:
        title = "Review Declined";
        sub = "Your application was rejected due to insufficient income records. You can check details or re-apply.";
        break;
    }

    return Column(
      children: [
        Text(title, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: darkText)),
        const SizedBox(height: 12),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 10),
          child: Text(
            sub,
            textAlign: TextAlign.center,
            style: TextStyle(fontSize: 15, color: Colors.grey.shade600, height: 1.5),
          ),
        ),
      ],
    );
  }

  Widget _buildActionButtons(BuildContext context) {
    // شيلنا الزحمة والـ PDF وخلينا فقط الأكشن المهم لكل حالة
    if (currentStatus == AppStatus.approved) {
      return _customButton("Choose Your Unit", Colors.green.shade700, Icons.home_work_rounded);
    } else if (currentStatus == AppStatus.rejected) {
      return _customButton("Edit & Re-submit", Colors.red.shade700, Icons.edit_document);
    } else {
      // في حالة الـ Pending أو الـ Submitted اليوزر بس "بيراقب" فممكن نشيل الزرار خالص أو نخليه للرجوع
      return _customButton("Back to Home", Colors.blueGrey, Icons.home_rounded);
    }
  }

  Widget _customButton(String text, Color color, IconData icon) {
    return SizedBox(
      width: double.infinity,
      child: ElevatedButton.icon(
        onPressed: () {},
        icon: Icon(icon, color: Colors.white),
        label: Text(text, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 16)),
        style: ElevatedButton.styleFrom(
          backgroundColor: color,
          padding: const EdgeInsets.symmetric(vertical: 20),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          elevation: 0,
        ),
      ),
    );
  }
}