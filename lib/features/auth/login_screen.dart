import 'package:flutter/material.dart';
import 'package:dio/dio.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:findoor_app2/core/api_config.dart';
import 'register_screen.dart';
import 'forgetpassword_screen.dart';
import 'package:findoor_app2/features/home/home_screen.dart';

class LoginScreen extends StatefulWidget {
  const LoginScreen({super.key});

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final _formKey = GlobalKey<FormState>();
  final _emailController    = TextEditingController();
  final _passwordController = TextEditingController();
  bool _isObscured = true;
  bool _isLoading  = false;

  @override
  void dispose() {
    _emailController.dispose();
    _passwordController.dispose();
    super.dispose();
  }

  Future<void> _handleLogin() async {
    if (!_formKey.currentState!.validate()) return;
    setState(() => _isLoading = true);
    try {
      final dio = Dio(BaseOptions(
        connectTimeout: const Duration(seconds: 15),
        receiveTimeout: const Duration(seconds: 15),
      ));
      final res = await dio.post(
        '${ApiConfig.nodeApi}/auth/login',
        data: {
          'email':    _emailController.text.trim(),
          'password': _passwordController.text,
        },
      );
      if (res.statusCode == 200 && res.data['success'] == true) {
        final token    = res.data['data']?['token']                as String? ?? '';
        final u        = res.data['data']?['user'] as Map? ?? {};
        final prefs    = await SharedPreferences.getInstance();
        await prefs.setString('auth_token',  token);
        await prefs.setString('user_name',   u['name']       as String? ?? '');
        await prefs.setString('user_email',  u['email']      as String? ?? '');
        await prefs.setString('user_phone',  u['phone']      as String? ?? '');
        await prefs.setString('user_nid',    u['nationalId'] as String? ?? '');
        if (mounted) {
          Navigator.pushReplacement(
            context,
            MaterialPageRoute(builder: (_) => const HomeScreen()),
          );
        }
      }
    } on DioException catch (e) {
      if (!mounted) return;
      final msg = e.type == DioExceptionType.connectionError
          ? 'Cannot reach server.\nEnsure your device and laptop are on the same Wi-Fi.'
          : (e.response?.data?['message'] as String? ?? 'Login failed. Check your credentials.');
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text(msg), backgroundColor: Colors.redAccent, behavior: SnackBarBehavior.floating),
      );
    } finally {
      if (mounted) setState(() => _isLoading = false);
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
              Container(
                height: 300,
                width: double.infinity,
                decoration: const BoxDecoration(
                  gradient: LinearGradient(
                    begin: Alignment.topLeft,
                    end: Alignment.bottomRight,
                    colors: [Color(0xFF1E88E5), Color(0xFF1565C0)],
                  ),
                  borderRadius: BorderRadius.only(bottomLeft: Radius.circular(60)),
                ),
                child: const Padding(
                  padding: EdgeInsets.symmetric(horizontal: 30),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      SizedBox(height: 40),
                      Icon(Icons.home_work_rounded, size: 60, color: Colors.white),
                      SizedBox(height: 20),
                      Text('Welcome Back',
                          style: TextStyle(fontSize: 32, fontWeight: FontWeight.bold, color: Colors.white)),
                      Text('Sign in to access housing services',
                          style: TextStyle(fontSize: 16, color: Colors.white70)),
                    ],
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.all(30),
                child: Column(
                  children: [
                    const SizedBox(height: 20),
                    _buildField(
                      label: 'Email Address',
                      icon: Icons.email_outlined,
                      hint: 'example@mail.com',
                      controller: _emailController,
                      keyboardType: TextInputType.emailAddress,
                      action: TextInputAction.next,
                      validator: (v) {
                        if (v == null || v.isEmpty) return 'Email is required';
                        if (!v.contains('@')) return 'Enter a valid email';
                        return null;
                      },
                    ),
                    const SizedBox(height: 20),
                    _buildField(
                      label: 'Password',
                      icon: Icons.lock_outline_rounded,
                      hint: '••••••••',
                      controller: _passwordController,
                      isPassword: true,
                      action: TextInputAction.done,
                      validator: (v) => (v == null || v.isEmpty) ? 'Password is required' : null,
                    ),
                    const SizedBox(height: 12),
                    Align(
                      alignment: Alignment.centerRight,
                      child: TextButton(
                        onPressed: () => Navigator.push(
                          context,
                          MaterialPageRoute(builder: (_) => const ForgotPasswordScreen()),
                        ),
                        child: const Text('Forgot Password?',
                            style: TextStyle(color: Color(0xFF1E88E5), fontWeight: FontWeight.w600)),
                      ),
                    ),
                    const SizedBox(height: 30),
                    SizedBox(
                      width: double.infinity,
                      height: 55,
                      child: ElevatedButton(
                        onPressed: _isLoading ? null : _handleLogin,
                        style: ElevatedButton.styleFrom(
                          backgroundColor: const Color(0xFF1E88E5),
                          foregroundColor: Colors.white,
                          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(15)),
                          elevation: 4,
                        ),
                        child: _isLoading
                            ? const SizedBox(
                                width: 20, height: 20,
                                child: CircularProgressIndicator(color: Colors.white, strokeWidth: 2),
                              )
                            : const Text('LOGIN',
                                style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, letterSpacing: 1.2)),
                      ),
                    ),
                    const SizedBox(height: 25),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Text("Don't have an account? ", style: TextStyle(color: Colors.grey.shade600)),
                        GestureDetector(
                          onTap: () => Navigator.push(
                            context,
                            MaterialPageRoute(builder: (_) => const RegisterScreen()),
                          ),
                          child: const Text('Create Account',
                              style: TextStyle(color: Color(0xFF1E88E5), fontWeight: FontWeight.bold)),
                        ),
                      ],
                    ),
                    const SizedBox(height: 40),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(Icons.verified_user, size: 16, color: Colors.grey.shade400),
                        const SizedBox(width: 8),
                        Text('End-to-end encrypted connection',
                            style: TextStyle(color: Colors.grey.shade400, fontSize: 12)),
                      ],
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildField({
    required String label,
    required IconData icon,
    required String hint,
    required TextEditingController controller,
    bool isPassword = false,
    TextInputAction? action,
    TextInputType? keyboardType,
    String? Function(String?)? validator,
  }) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label,
            style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600, color: Color(0xFF263238))),
        const SizedBox(height: 8),
        TextFormField(
          controller: controller,
          obscureText: isPassword ? _isObscured : false,
          textInputAction: action,
          keyboardType: keyboardType,
          validator: validator,
          decoration: InputDecoration(
            hintText: hint,
            hintStyle: TextStyle(color: Colors.grey.shade400, fontSize: 14),
            prefixIcon: Icon(icon, color: const Color(0xFF1E88E5), size: 22),
            suffixIcon: isPassword
                ? IconButton(
                    icon: Icon(_isObscured ? Icons.visibility_off : Icons.visibility,
                        color: Colors.grey, size: 20),
                    onPressed: () => setState(() => _isObscured = !_isObscured),
                  )
                : null,
            filled: true,
            fillColor: Colors.white,
            errorStyle: const TextStyle(color: Colors.redAccent),
            enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(15),
                borderSide: BorderSide(color: Colors.grey.shade200)),
            focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(15),
                borderSide: const BorderSide(color: Color(0xFF1E88E5), width: 2)),
            errorBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(15),
                borderSide: const BorderSide(color: Colors.redAccent)),
            focusedErrorBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(15),
                borderSide: const BorderSide(color: Colors.redAccent, width: 2)),
          ),
        ),
      ],
    );
  }
}
