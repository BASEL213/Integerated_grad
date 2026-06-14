import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

class WalletPage extends StatefulWidget {
  const WalletPage({super.key});

  @override
  State<WalletPage> createState() => _WalletPageState();
}

class _WalletPageState extends State<WalletPage> {
  static const Color primaryBlue = Color(0xFF1E88E5);
  static const Color darkText    = Color(0xFF263238);

  String _userName = '';

  @override
  void initState() {
    super.initState();
    _loadName();
  }

  Future<void> _loadName() async {
    final prefs = await SharedPreferences.getInstance();
    if (mounted) setState(() => _userName = prefs.getString('user_name') ?? 'Member');
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
        title: const Text('My Wallet',
            style: TextStyle(color: darkText, fontWeight: FontWeight.bold, fontSize: 18)),
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.all(24),
        child: Column(
          children: [
            _buildCreditCard(),
            const SizedBox(height: 32),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceAround,
              children: [
                _walletAction(Icons.add,           'Top Up'),
                _walletAction(Icons.send_rounded,  'Transfer'),
                _walletAction(Icons.history,       'Report'),
              ],
            ),
            const SizedBox(height: 32),
            const Align(
              alignment: Alignment.centerLeft,
              child: Text('Recent Transactions',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: darkText)),
            ),
            const SizedBox(height: 16),
            _transactionItem('Application Fee', '- EGP 150.00',   '04 April', Colors.redAccent),
            _transactionItem('Wallet Top-up',   '+ EGP 2,000.00', '01 April', Colors.green),
            _transactionItem('Unit Deposit',    '- EGP 1,200.00', '28 March', Colors.redAccent),
          ],
        ),
      ),
    );
  }

  Widget _buildCreditCard() {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(
        gradient: const LinearGradient(
          colors: [Color(0xFF1E88E5), Color(0xFF1565C0)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        borderRadius: BorderRadius.circular(28),
        boxShadow: [
          BoxShadow(
            color: const Color(0xFF1E88E5).withValues(alpha: 0.35),
            blurRadius: 20,
            offset: const Offset(0, 10),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          const Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text('Current Balance',
                  style: TextStyle(color: Colors.white70, fontSize: 14)),
              Icon(Icons.contactless, color: Colors.white54),
            ],
          ),
          const SizedBox(height: 8),
          const Text('EGP 12,450.00',
              style: TextStyle(
                  color: Colors.white, fontSize: 32, fontWeight: FontWeight.bold)),
          const SizedBox(height: 40),
          const Text('**** **** **** 8820',
              style: TextStyle(
                  color: Colors.white, fontSize: 18, letterSpacing: 2)),
          const SizedBox(height: 12),
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              Text(_userName,
                  style: const TextStyle(color: Colors.white70)),
              const Text('12/28',
                  style: TextStyle(color: Colors.white70)),
            ],
          ),
        ],
      ),
    );
  }

  Widget _walletAction(IconData icon, String label) {
    return Column(
      children: [
        Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: Colors.white,
            shape: BoxShape.circle,
            boxShadow: [
              BoxShadow(
                  color: Colors.black.withValues(alpha: 0.05), blurRadius: 10),
            ],
          ),
          child: Icon(icon, color: primaryBlue),
        ),
        const SizedBox(height: 8),
        Text(label,
            style: const TextStyle(
                fontSize: 12, fontWeight: FontWeight.w600, color: darkText)),
      ],
    );
  }

  Widget _transactionItem(
      String title, String amount, String date, Color color) {
    return Container(
      margin: const EdgeInsets.only(bottom: 12),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
          color: Colors.white, borderRadius: BorderRadius.circular(20)),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
                color: color.withValues(alpha: 0.1), shape: BoxShape.circle),
            child: Icon(Icons.receipt_long, color: color, size: 20),
          ),
          const SizedBox(width: 16),
          Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(title,
                style: const TextStyle(
                    fontWeight: FontWeight.bold, color: darkText)),
            Text(date,
                style: const TextStyle(color: Colors.grey, fontSize: 12)),
          ]),
          const Spacer(),
          Text(amount,
              style:
                  TextStyle(fontWeight: FontWeight.bold, color: color)),
        ],
      ),
    );
  }
}
