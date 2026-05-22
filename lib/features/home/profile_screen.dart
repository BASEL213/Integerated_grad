import 'package:flutter/material.dart';

class ProfilePage extends StatelessWidget {
  const ProfilePage({super.key});

  // Consistency with your existing palette
  static const Color primaryBlue = Color(0xFF1E88E5);
  static const Color darkText = Color(0xFF263238);
  static const Color premiumBackground = Color(0xFFF8FAFC);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: premiumBackground,
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_new, color: darkText, size: 20),
          onPressed: () => Navigator.pop(context),
        ),
        title: const Text("My Profile",
            style: TextStyle(color: darkText, fontWeight: FontWeight.bold, fontSize: 18)),
        actions: [
          IconButton(
            icon: const Icon(Icons.edit_outlined, color: primaryBlue),
            onPressed: () {},
          ),
        ],
      ),
      body: SingleChildScrollView(
        padding: const EdgeInsets.symmetric(horizontal: 24),
        child: Column(
          children: [
            const SizedBox(height: 20),

            // --- 1. Profile Header ---
            _buildProfileAvatar(),

            const SizedBox(height: 16),
            const Text("Ahmed Mohamed",
                style: TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: darkText)),
            const Text("Electrical Engineer",
                style: TextStyle(fontSize: 14, color: Colors.grey)),

            const SizedBox(height: 32),

            // --- 2. Personal Information Section ---
            _buildSectionHeader("Personal Information"),
            _buildProfileCard([
              _buildProfileItem(Icons.email_outlined, "Email", "ahmed.m@example.com"),
              _buildDivider(),
              _buildProfileItem(Icons.phone_android_outlined, "Phone", "+20 123 456 7890"),
              _buildDivider(),
              _buildProfileItem(Icons.location_on_outlined, "Location", "New Cairo, Egypt"),
            ]),

            const SizedBox(height: 24),

            // --- 3. Account Settings Section ---
            _buildSectionHeader("Account Settings"),
            _buildProfileCard([
              _buildProfileItem(Icons.shield_outlined, "Security", "Password & ID"),
              _buildDivider(),
              _buildProfileItem(Icons.notifications_none_outlined, "Notifications", "Mute/Unmute"),
              _buildDivider(),
              _buildProfileItem(Icons.language_outlined, "Language", "English (Academic)"),
            ]),

            const SizedBox(height: 32),

            // --- 4. Logout Button ---
            SizedBox(
              width: double.infinity,
              child: TextButton.icon(
                onPressed: () {},
                icon: const Icon(Icons.logout_rounded, color: Colors.redAccent),
                label: const Text("Logout from Account",
                    style: TextStyle(color: Colors.redAccent, fontWeight: FontWeight.bold)),
                style: TextButton.styleFrom(
                  padding: const EdgeInsets.symmetric(vertical: 16),
                  backgroundColor: Colors.redAccent.withValues(alpha: 0.1),
                  shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(15)),
                ),
              ),
            ),
            const SizedBox(height: 40),
          ],
        ),
      ),
    );
  }

  Widget _buildProfileAvatar() {
    return Stack(
      alignment: Alignment.bottomRight,
      children: [
        Container(
          padding: const EdgeInsets.all(4),
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            border: Border.all(color: primaryBlue.withValues(alpha: 0.2), width: 2),
          ),
          child: const CircleAvatar(
            radius: 60,
            backgroundColor: primaryBlue,
            child: Icon(Icons.person, color: Colors.white, size: 70),
          ),
        ),
        Container(
          padding: const EdgeInsets.all(8),
          decoration: const BoxDecoration(color: primaryBlue, shape: BoxShape.circle),
          child: const Icon(Icons.camera_alt, color: Colors.white, size: 20),
        ),
      ],
    );
  }

  Widget _buildSectionHeader(String title) {
    return Padding(
      padding: const EdgeInsets.only(left: 4, bottom: 12),
      child: Align(
        alignment: Alignment.centerLeft,
        child: Text(title,
            style: const TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: darkText)),
      ),
    );
  }

  Widget _buildProfileCard(List<Widget> children) {
    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(24),
        boxShadow: [
          BoxShadow(color: Colors.black.withValues(alpha: 0.03), blurRadius: 20, offset: const Offset(0, 10)),
        ],
      ),
      child: Column(children: children),
    );
  }

  Widget _buildProfileItem(IconData icon, String label, String value) {
    return Padding(
      padding: const EdgeInsets.all(16),
      child: Row(
        children: [
          Container(
            padding: const EdgeInsets.all(10),
            decoration: BoxDecoration(
              color: premiumBackground,
              borderRadius: BorderRadius.circular(12),
            ),
            child: Icon(icon, color: primaryBlue, size: 22),
          ),
          const SizedBox(width: 16),
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(label, style: const TextStyle(fontSize: 12, color: Colors.grey)),
              Text(value, style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w600, color: darkText)),
            ],
          ),
          const Spacer(),
          const Icon(Icons.arrow_forward_ios, color: Colors.grey, size: 14),
        ],
      ),
    );
  }

  Widget _buildDivider() {
    return Divider(height: 1, indent: 70, endIndent: 16, color: Colors.grey.shade100);
  }
}