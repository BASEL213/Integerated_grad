import 'package:flutter/material.dart';
import 'package:dio/dio.dart';
import 'package:findoor_app2/core/api_config.dart';
import 'package:findoor_app2/features/home/nid_scan_screen.dart';

class RegisterScreen extends StatefulWidget {
  const RegisterScreen({super.key});

  @override
  State<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends State<RegisterScreen> {
  final _formKey             = GlobalKey<FormState>();
  final _nameController      = TextEditingController();
  final _emailController     = TextEditingController();
  final _phoneController     = TextEditingController();
  final _idController        = TextEditingController();
  final _passController      = TextEditingController();
  final _confirmPassController = TextEditingController();

  bool _obscurePass        = true;
  bool _obscureConfirmPass = true;
  bool _nidScanned         = false;
  bool _isLoading          = false;

  @override
  void dispose() {
    _nameController.dispose();
    _emailController.dispose();
    _phoneController.dispose();
    _idController.dispose();
    _passController.dispose();
    _confirmPassController.dispose();
    super.dispose();
  }

  Future<void> _handleNidScan() async {
    final result = await Navigator.push<Map<String, String>>(
      context,
      MaterialPageRoute(builder: (_) => const NIDScanScreen()),
    );
    if (result == null || !mounted) return;
    setState(() {
      if (result['name']?.isNotEmpty == true)       _nameController.text = result['name']!;
      if (result['nationalId']?.isNotEmpty == true) _idController.text   = result['nationalId']!;
      _nidScanned = true;
    });
  }

  Future<void> _handleRegister() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _isLoading = true);
    try {
      final dio = Dio(BaseOptions(
        connectTimeout: const Duration(seconds: 15),
        receiveTimeout: const Duration(seconds: 15),
      ));
      final res = await dio.post(
        '${ApiConfig.nodeApi}/auth/register',
        data: {
          'name':       _nameController.text.trim(),
          'email':      _emailController.text.trim(),
          'password':   _passController.text,
          'phone':      _phoneController.text.trim(),
          'nationalId': _idController.text.trim(),
        },
      );
      if ((res.statusCode == 200 || res.statusCode == 201) &&
          res.data['success'] == true) {
        if (mounted) _showSuccessDialog();
      }
    } on DioException catch (e) {
      if (!mounted) return;
      final msg = e.type == DioExceptionType.connectionError
          ? 'Cannot reach server.\nEnsure your device and laptop are on the same Wi-Fi.'
          : (e.response?.data?['message'] as String? ?? 'Registration failed. Please try again.');
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(msg), backgroundColor: Colors.redAccent, behavior: SnackBarBehavior.floating),
      );
    } finally {
      if (mounted) setState(() => _isLoading = false);
    }
  }

  void _showSuccessDialog() {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.check_circle_rounded, color: Colors.green, size: 70),
            const SizedBox(height: 15),
            const Text('Account Created!', style: TextStyle(fontWeight: FontWeight.bold, fontSize: 22)),
            const SizedBox(height: 10),
            const Text('Welcome to Findoor. Your registration is complete.',
                textAlign: TextAlign.center, style: TextStyle(color: Colors.grey)),
            const SizedBox(height: 25),
            SizedBox(
              width: double.infinity,
              child: ElevatedButton(
                style: ElevatedButton.styleFrom(
                  backgroundColor: const Color(0xFF1E88E5),
                  padding: const EdgeInsets.symmetric(vertical: 12),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(10)),
                ),
                onPressed: () {
                  Navigator.pop(ctx);
                  Navigator.pop(context);
                },
                child: const Text('Go to Login', style: TextStyle(color: Colors.white, fontSize: 16)),
              ),
            ),
          ],
        ),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF8FAFC),
      body: SingleChildScrollView(
        child: Form(
          key: _formKey,
          child: Column(
            children: [
              _buildHeader(),
              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 25, vertical: 20),
                child: Column(
                  children: [
                    _buildInput(label: 'Full Name',      icon: Icons.person_outline,     hint: 'As written in your ID', controller: _nameController),
                    const SizedBox(height: 15),
                    _buildInput(label: 'Email Address',  icon: Icons.email_outlined,     hint: 'example@mail.com',      controller: _emailController, isEmail: true),
                    const SizedBox(height: 15),
                    _buildInput(label: 'National ID',    icon: Icons.badge_outlined,     hint: '14 digits number',      controller: _idController,    isID: true),
                    const SizedBox(height: 10),
                    _buildScanButton(),
                    const SizedBox(height: 15),
                    _buildInput(label: 'Phone Number',   icon: Icons.phone_android_rounded, hint: '01xxxxxxxxx',        controller: _phoneController, isPhone: true),
                    const SizedBox(height: 15),
                    _buildInput(
                      label: 'Password', icon: Icons.lock_outline, hint: '••••••••',
                      controller: _passController, isPassword: true,
                      obscure: _obscurePass, onToggle: () => setState(() => _obscurePass = !_obscurePass),
                    ),
                    const SizedBox(height: 15),
                    _buildInput(
                      label: 'Confirm Password', icon: Icons.lock_reset_rounded, hint: 'Re-enter password',
                      controller: _confirmPassController, isPassword: true,
                      obscure: _obscureConfirmPass, onToggle: () => setState(() => _obscureConfirmPass = !_obscureConfirmPass),
                      validator: (v) => v != _passController.text ? 'Passwords do not match' : null,
                    ),
                    const SizedBox(height: 35),
                    _buildRegisterButton(),
                    const SizedBox(height: 10),
                    TextButton(
                      onPressed: () => Navigator.pop(context),
                      child: const Text('Already have an account? Login',
                          style: TextStyle(color: Color(0xFF1E88E5), fontWeight: FontWeight.w600)),
                    ),
                    const SizedBox(height: 20),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildHeader() => Container(
        height: 200,
        width: double.infinity,
        decoration: const BoxDecoration(
          gradient: LinearGradient(colors: [Color(0xFF1E88E5), Color(0xFF1565C0)]),
          borderRadius: BorderRadius.only(bottomLeft: Radius.circular(80)),
        ),
        child: const Padding(
          padding: EdgeInsets.only(left: 30, top: 40),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Create Account', style: TextStyle(fontSize: 32, fontWeight: FontWeight.bold, color: Colors.white)),
              Text('Start your journey with Findoor', style: TextStyle(fontSize: 16, color: Colors.white70)),
            ],
          ),
        ),
      );

  Widget _buildInput({
    required String label,
    required IconData icon,
    required String hint,
    required TextEditingController controller,
    bool isPassword = false, bool isID = false,
    bool isEmail = false,    bool isPhone = false,
    bool obscure = false,    VoidCallback? onToggle,
    String? Function(String?)? validator,
  }) =>
      Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.only(left: 5, bottom: 5),
            child: Text(label, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13, color: Color(0xFF455A64))),
          ),
          TextFormField(
            controller: controller,
            obscureText: obscure,
            keyboardType: (isID || isPhone)
                ? TextInputType.number
                : (isEmail ? TextInputType.emailAddress : TextInputType.text),
            validator: validator ??
                (v) {
                  if (v == null || v.isEmpty) return 'This field is required';
                  if (isID && v.length != 14) return 'National ID must be 14 digits';
                  if (isPhone && v.length < 11) return 'Invalid phone number';
                  if (isEmail && !v.contains('@')) return 'Enter a valid email';
                  return null;
                },
            decoration: InputDecoration(
              hintText: hint,
              hintStyle: TextStyle(color: Colors.grey.shade400, fontSize: 14),
              prefixIcon: Icon(icon, color: const Color(0xFF1E88E5), size: 22),
              suffixIcon: isPassword
                  ? IconButton(
                      icon: Icon(obscure ? Icons.visibility_off : Icons.visibility, color: Colors.grey),
                      onPressed: onToggle)
                  : null,
              filled: true,
              fillColor: Colors.white,
              contentPadding: const EdgeInsets.symmetric(vertical: 16),
              enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12), borderSide: BorderSide(color: Colors.grey.shade200)),
              focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: Color(0xFF1E88E5), width: 1.5)),
              errorBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: Colors.redAccent)),
              focusedErrorBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: Colors.redAccent, width: 1.5)),
            ),
          ),
        ],
      );

  Widget _buildScanButton() => GestureDetector(
        onTap: _handleNidScan,
        child: Container(
          width: double.infinity,
          padding: const EdgeInsets.symmetric(vertical: 13, horizontal: 16),
          decoration: BoxDecoration(
            color: _nidScanned
                ? Colors.green.withValues(alpha: 0.08)
                : const Color(0xFF1E88E5).withValues(alpha: 0.07),
            borderRadius: BorderRadius.circular(12),
            border: Border.all(
              color: _nidScanned
                  ? Colors.green.withValues(alpha: 0.4)
                  : const Color(0xFF1E88E5).withValues(alpha: 0.35),
            ),
          ),
          child: Row(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(
                _nidScanned ? Icons.check_circle_rounded : Icons.document_scanner_rounded,
                color: _nidScanned ? Colors.green : const Color(0xFF1E88E5),
                size: 20,
              ),
              const SizedBox(width: 10),
              Text(
                _nidScanned ? 'NID Scanned — tap to re-scan' : 'Scan NID to auto-fill Name & ID',
                style: TextStyle(
                  color: _nidScanned ? Colors.green : const Color(0xFF1E88E5),
                  fontWeight: FontWeight.w600, fontSize: 13,
                ),
              ),
            ],
          ),
        ),
      );

  Widget _buildRegisterButton() => Container(
        width: double.infinity,
        height: 55,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(12),
          boxShadow: [BoxShadow(color: const Color(0xFF1E88E5).withValues(alpha: 0.3), blurRadius: 10, offset: const Offset(0, 5))],
        ),
        child: ElevatedButton(
          onPressed: _isLoading ? null : _handleRegister,
          style: ElevatedButton.styleFrom(
            backgroundColor: const Color(0xFF1E88E5),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
            elevation: 0,
          ),
          child: _isLoading
              ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2))
              : const Text('CREATE ACCOUNT',
                  style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 16, letterSpacing: 1.1)),
        ),
      );
}
