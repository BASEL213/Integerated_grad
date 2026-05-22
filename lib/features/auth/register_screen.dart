import 'package:flutter/material.dart';
import 'package:findoor_app2/features/home/nid_scan_screen.dart';

class RegisterScreen extends StatefulWidget {
  const RegisterScreen({super.key});

  @override
  State<RegisterScreen> createState() => _RegisterScreenState();
}

class _RegisterScreenState extends State<RegisterScreen> {
  final _formKey = GlobalKey<FormState>();

  // Controllers
  final TextEditingController _nameController = TextEditingController();
  final TextEditingController _emailController = TextEditingController();
  final TextEditingController _phoneController = TextEditingController();
  final TextEditingController _idController = TextEditingController();
  final TextEditingController _passController = TextEditingController();
  final TextEditingController _confirmPassController = TextEditingController();

  bool _obscurePass = true;
  bool _obscureConfirmPass = true;
  bool _nidScanned = false;

  Future<void> _handleNidScan() async {
    final result = await Navigator.push<Map<String, String>>(
      context,
      MaterialPageRoute(builder: (_) => const NIDScanScreen()),
    );
    if (result == null || !mounted) return;
    setState(() {
      if (result['name']?.isNotEmpty == true) {
        _nameController.text = result['name']!;
      }
      if (result['nationalId']?.isNotEmpty == true) {
        _idController.text = result['nationalId']!;
      }
      _nidScanned = true;
    });
  }

  void _handleRegister() {
    // الزرار مش هيفتح الـ Dialog غير لو الـ Form كلها Validate
    if (_formKey.currentState!.validate()) {
      showDialog(
        context: context,
        barrierDismissible: false,
        builder: (context) => AlertDialog(
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Icon(Icons.check_circle_rounded, color: Colors.green, size: 70),
              const SizedBox(height: 15),
              const Text(
                "Account Created!",
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 22),
              ),
              const SizedBox(height: 10),
              const Text(
                "Welcome to Findoor. Your registration is complete.",
                textAlign: TextAlign.center,
                style: TextStyle(color: Colors.grey),
              ),
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
                    Navigator.pop(context); // قفل الدايلوج
                    Navigator.pop(context); // الرجوع للوجين
                  },
                  child: const Text("Go to Login", style: TextStyle(color: Colors.white, fontSize: 16)),
                ),
              )
            ],
          ),
        ),
      );
    }
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
              // --- Header ---
              _buildHeader(),

              Padding(
                padding: const EdgeInsets.symmetric(horizontal: 25, vertical: 20),
                child: Column(
                  children: [
                    _buildInput(
                      label: "Full Name",
                      icon: Icons.person_outline,
                      hint: "As written in your ID",
                      controller: _nameController,
                    ),
                    const SizedBox(height: 15),
                    _buildInput(
                      label: "Email Address",
                      icon: Icons.email_outlined,
                      hint: "example@mail.com",
                      controller: _emailController,
                      isEmail: true,
                    ),
                    const SizedBox(height: 15),
                    _buildInput(
                      label: "National ID",
                      icon: Icons.badge_outlined,
                      hint: "14 digits number",
                      controller: _idController,
                      isID: true,
                    ),
                    const SizedBox(height: 10),
                    _buildScanNidButton(),
                    const SizedBox(height: 15),
                    _buildInput(
                      label: "Phone Number",
                      icon: Icons.phone_android_rounded,
                      hint: "01xxxxxxxxx",
                      controller: _phoneController,
                      isPhone: true,
                    ),
                    const SizedBox(height: 15),
                    _buildInput(
                      label: "Password",
                      icon: Icons.lock_outline,
                      hint: "••••••••",
                      controller: _passController,
                      isPassword: true,
                      obscure: _obscurePass,
                      onToggle: () => setState(() => _obscurePass = !_obscurePass),
                    ),
                    const SizedBox(height: 15),
                    _buildInput(
                      label: "Confirm Password",
                      icon: Icons.lock_reset_rounded,
                      hint: "Re-enter password",
                      controller: _confirmPassController,
                      isPassword: true,
                      obscure: _obscureConfirmPass,
                      onToggle: () => setState(() => _obscureConfirmPass = !_obscureConfirmPass),
                      validator: (value) {
                        if (value != _passController.text) return "Passwords do not match";
                        return null;
                      },
                    ),
                    const SizedBox(height: 35),

                    // --- Register Button ---
                    _buildRegisterButton(),

                    const SizedBox(height: 10),
                    TextButton(
                      onPressed: () => Navigator.pop(context),
                      child: const Text("Already have an account? Login",
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

  // Header Widget
  Widget _buildHeader() {
    return Container(
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
            Text("Create Account", style: TextStyle(fontSize: 32, fontWeight: FontWeight.bold, color: Colors.white)),
            Text("Start your journey with Findoor", style: TextStyle(fontSize: 16, color: Colors.white70)),
          ],
        ),
      ),
    );
  }

  // Integrated Input Widget
  Widget _buildInput({
    required String label,
    required IconData icon,
    required String hint,
    required TextEditingController controller,
    bool isPassword = false,
    bool isID = false,
    bool isEmail = false,
    bool isPhone = false,
    bool obscure = false,
    VoidCallback? onToggle,
    String? Function(String?)? validator,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Padding(
          padding: const EdgeInsets.only(left: 5, bottom: 5),
          child: Text(label, style: const TextStyle(fontWeight: FontWeight.w600, fontSize: 13, color: Color(0xFF455A64))),
        ),
        TextFormField(
          controller: controller,
          obscureText: obscure,
          keyboardType: (isID || isPhone) ? TextInputType.number : (isEmail ? TextInputType.emailAddress : TextInputType.text),
          validator: validator ?? (value) {
            if (value == null || value.isEmpty) return 'This field is required';
            if (isID && value.length != 14) return 'National ID must be 14 digits';
            if (isPhone && value.length < 11) return 'Invalid phone number';
            if (isEmail && !value.contains('@')) return 'Enter a valid email';
            return null;
          },
          decoration: InputDecoration(
            hintText: hint,
            hintStyle: TextStyle(color: Colors.grey.shade400, fontSize: 14),
            prefixIcon: Icon(icon, color: const Color(0xFF1E88E5), size: 22),
            suffixIcon: isPassword
                ? IconButton(icon: Icon(obscure ? Icons.visibility_off : Icons.visibility, color: Colors.grey), onPressed: onToggle)
                : null,
            filled: true,
            fillColor: Colors.white,
            contentPadding: const EdgeInsets.symmetric(vertical: 16),
            enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide(color: Colors.grey.shade200)),
            focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: Color(0xFF1E88E5), width: 1.5)),
            errorBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: Colors.redAccent)),
            focusedErrorBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: Colors.redAccent, width: 1.5)),
          ),
        ),
      ],
    );
  }

  Widget _buildScanNidButton() {
    return GestureDetector(
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
              _nidScanned
                  ? Icons.check_circle_rounded
                  : Icons.document_scanner_rounded,
              color: _nidScanned ? Colors.green : const Color(0xFF1E88E5),
              size: 20,
            ),
            const SizedBox(width: 10),
            Text(
              _nidScanned
                  ? 'NID Scanned — tap to re-scan'
                  : 'Scan NID to auto-fill Name & ID',
              style: TextStyle(
                color: _nidScanned ? Colors.green : const Color(0xFF1E88E5),
                fontWeight: FontWeight.w600,
                fontSize: 13,
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildRegisterButton() {
    return Container(
      width: double.infinity,
      height: 55,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(12),
        boxShadow: [
          BoxShadow(color: const Color(0xFF1E88E5).withValues(alpha: 0.3), blurRadius: 10, offset: const Offset(0, 5))
        ],
      ),
      child: ElevatedButton(
        onPressed: _handleRegister,
        style: ElevatedButton.styleFrom(
          backgroundColor: const Color(0xFF1E88E5),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
          elevation: 0,
        ),
        child: const Text("CREATE ACCOUNT", style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 16, letterSpacing: 1.1)),
      ),
    );
  }
}