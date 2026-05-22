import 'package:flutter/material.dart';
import 'theme.dart';
import '../features/splash/splash_screen.dart';

class FindoorApp extends StatelessWidget {
  const FindoorApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      title: 'Findoor',
      theme: AppTheme.lightTheme,
      home: const SplashScreen(),
    );
  }
}
