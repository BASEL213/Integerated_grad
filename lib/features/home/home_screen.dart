import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:dio/dio.dart';
import 'package:findoor_app2/core/api_config.dart';
import 'application_page.dart';
import 'profile_screen.dart';
import 'search_screen.dart';
import 'status_screen.dart';
import 'wallet_screen.dart';
import 'projects_screen.dart';
import 'property_details_screen.dart';
import 'chatbot_screen.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  // Professional color palette
  static const Color primaryBlue = Color(0xFF1E88E5);

  String _userName     = '';
  String _trackingCode = '';
  List<Map<String, dynamic>> _featuredProjects = [];
  bool _loadingFeatured = false;

  @override
  void initState() {
    super.initState();
    _loadPrefs();
    _fetchFeaturedProjects();
  }

  Future<void> _loadPrefs() async {
    final prefs = await SharedPreferences.getInstance();
    if (mounted) {
      setState(() {
        _userName     = prefs.getString('user_name')     ?? '';
        _trackingCode = prefs.getString('tracking_code') ?? '';
      });
    }
  }

  Future<void> _fetchFeaturedProjects() async {
    setState(() => _loadingFeatured = true);
    try {
      final res = await Dio().get('${ApiConfig.nodeApi}/projects',
          queryParameters: {'limit': 5});
      final list = res.data is List
          ? res.data as List
          : (res.data['data'] as List? ?? []);
      if (mounted) {
        setState(() {
          _featuredProjects = list
              .map((p) => Map<String, dynamic>.from(p as Map))
              .toList();
        });
      }
    } catch (_) {
      // keep empty — carousel shows placeholder
    } finally {
      if (mounted) setState(() => _loadingFeatured = false);
    }
  }
  static const Color darkBlue = Color(0xFF1565C0);
  static const Color premiumBackground = Color(0xFFF8FAFC);
  static const Color darkText = Color(0xFF263238);


  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: premiumBackground,
      // --- ADDED AI RECOMMENDATION ICON HERE ---
      floatingActionButton: Padding(
        padding: const EdgeInsets.only(bottom: 90), // Offset to stay above the floating nav bar
        child: FloatingActionButton(
          onPressed: () {
            Navigator.push(
              context,
              MaterialPageRoute(builder: (context) => const ChatbotPage()),
            );
          },
          backgroundColor: darkText,
          elevation: 4,
          shape: const CircleBorder(),
          child: Container(
            width: 60,
            height: 60,
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: LinearGradient(
                colors: [primaryBlue, Colors.purple.shade400],
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
              ),
            ),
            child: const Icon(Icons.auto_awesome, color: Colors.white, size: 28),
          ),
        ),
      ),
      body: Stack(
        children: [
          SingleChildScrollView(
            physics: const BouncingScrollPhysics(),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const SizedBox(height: 60),
                _buildHeader(),
                const SizedBox(height: 24),
                _buildQuickServices(),
                const SizedBox(height: 32),
                const Padding(
                  padding: EdgeInsets.symmetric(horizontal: 24),
                  child: Text(
                    "Featured Properties",
                    style: TextStyle(
                      fontSize: 22,
                      fontWeight: FontWeight.bold,
                      color: darkText,
                      letterSpacing: -0.5,
                    ),
                  ),
                ),
                const SizedBox(height: 16),
                _buildPropertyCarousel(),
                const SizedBox(height: 120),
              ],
            ),
          ),
          _buildFloatingNavBar(),
        ],
      ),
    );
  }

  Widget _buildHeader() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(_userName.isNotEmpty ? 'Hi $_userName' : 'Hi there', style: const TextStyle(color: Colors.grey, fontSize: 16)),
              const Text("Good Morning,",
                  style: TextStyle(fontSize: 28, fontWeight: FontWeight.bold, color: darkText, letterSpacing: -0.5)),
            ],
          ),
          GestureDetector(
            onTap: () => Navigator.push(context, MaterialPageRoute(builder: (context) => const ProfilePage())),
            child: Tooltip(
              message: "View Profile",
              child: Stack(
                children: [
                  Container(
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      border: Border.all(color: primaryBlue.withValues(alpha: 0.2), width: 2),
                    ),
                    child: const CircleAvatar(
                      radius: 25,
                      backgroundColor: primaryBlue,
                      child: Icon(Icons.person, color: Colors.white, size: 30),
                    ),
                  ),
                  const Positioned(
                    right: 0,
                    top: 0,
                    child: CircleAvatar(
                        radius: 8,
                        backgroundColor: Colors.orange,
                        child: Text("3", style: TextStyle(color: Colors.white, fontSize: 9, fontWeight: FontWeight.bold))
                    ),
                  )
                ],
              ),
            ),
          )
        ],
      ),
    );
  }

  Widget _buildQuickServices() {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 24),
      child: Row(
        children: [
          Expanded(
            child: Tooltip(
              message: "Start a new housing application",
              child: InkWell(
                onTap: () {
                  Navigator.push(context, MaterialPageRoute(builder: (context) => const ApplicationPage()));
                },
                borderRadius: BorderRadius.circular(24),
                child: Container(
                  height: 180,
                  padding: const EdgeInsets.all(20),
                  decoration: BoxDecoration(
                    gradient: const LinearGradient(colors: [primaryBlue, darkBlue], begin: Alignment.topLeft, end: Alignment.bottomRight),
                    borderRadius: BorderRadius.circular(24),
                    boxShadow: [
                      BoxShadow(color: primaryBlue.withValues(alpha: 0.3), blurRadius: 15, offset: const Offset(0, 5)),
                    ],
                  ),
                  child: const Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    mainAxisAlignment: MainAxisAlignment.end,
                    children: [
                      Icon(Icons.add_home_work_outlined, color: Colors.white, size: 40),
                      Spacer(),
                      Text("Apply Now", style: TextStyle(color: Colors.white, fontSize: 20, fontWeight: FontWeight.bold, letterSpacing: 0.5)),
                      Text("Start New Application", style: TextStyle(color: Colors.white70, fontSize: 12)),
                    ],
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(width: 16),
          Expanded(
            child: Column(
              children: [
                _buildSmallStatusCard("My Status", Icons.auto_graph, Colors.orange, "Track your application status", () {
                  if (_trackingCode.isEmpty) {
                    ScaffoldMessenger.of(context).showSnackBar(
                      const SnackBar(content: Text('No application submitted yet.'), behavior: SnackBarBehavior.floating),
                    );
                    return;
                  }
                  Navigator.push(context, MaterialPageRoute(builder: (_) => StatusPage(trackingCode: _trackingCode)));
                }),
                const SizedBox(height: 16),
                _buildSmallStatusCard("E-Wallet", Icons.account_balance_wallet, Colors.green, "View balance and payments", () {
                  Navigator.push(context, MaterialPageRoute(builder: (context) => const WalletPage()));
                }),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSmallStatusCard(String title, IconData icon, Color accentColor, String tooltip, VoidCallback onTap) {
    return Tooltip(
      message: tooltip,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(20),
        child: Container(
          padding: const EdgeInsets.all(16),
          decoration: BoxDecoration(
            color: Colors.white,
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: Colors.grey.shade100),
            boxShadow: [
              BoxShadow(color: Colors.black.withValues(alpha: 0.05), blurRadius: 10, offset: const Offset(0, 5)),
            ],
          ),
          child: Row(
            children: [
              Icon(icon, color: accentColor),
              const SizedBox(width: 12),
              Text(title, style: const TextStyle(fontWeight: FontWeight.bold, color: darkText)),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildPropertyCarousel() {
    if (_loadingFeatured) {
      return const SizedBox(
        height: 380,
        child: Center(child: CircularProgressIndicator(color: primaryBlue)),
      );
    }
    if (_featuredProjects.isEmpty) {
      return SizedBox(
        height: 200,
        child: Center(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.apartment_outlined, size: 48, color: Colors.grey.shade300),
              const SizedBox(height: 12),
              Text('No projects available',
                  style: TextStyle(color: Colors.grey.shade400, fontSize: 14)),
            ],
          ),
        ),
      );
    }
    return SizedBox(
      height: 380,
      child: PageView.builder(
        controller: PageController(viewportFraction: 0.9),
        itemCount: _featuredProjects.length,
        itemBuilder: (context, index) {
          final p = _featuredProjects[index];
          final title    = (p['name'] ?? p['title'] ?? 'Project').toString();
          final location = (p['location'] ?? p['governorate'] ?? 'Egypt').toString();
          final price    = p['price'] != null ? 'EGP ${p['price']}' : 'On request';
          final imageUrl = (p['imageUrl'] ?? p['image'] ?? '').toString();
          return InkWell(
            onTap: () => Navigator.push(
              context,
              MaterialPageRoute(
                builder: (_) => PropertyDetailsPage(property: {
                  'title':    title,
                  'location': location,
                  'price':    price,
                  'beds':     (p['bedrooms']  ?? p['beds']  ?? '—').toString(),
                  'baths':    (p['bathrooms'] ?? p['baths'] ?? '—').toString(),
                  'sqft':     (p['area']      ?? p['sqft']  ?? '—').toString(),
                  'image':    imageUrl,
                }),
              ),
            ),
            borderRadius: BorderRadius.circular(32),
            child: Container(
              margin: const EdgeInsets.only(right: 20, bottom: 20),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(32),
                boxShadow: [
                  BoxShadow(
                      color: Colors.black.withValues(alpha: 0.04),
                      blurRadius: 20,
                      offset: const Offset(0, 10)),
                ],
              ),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(32),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Stack(
                      children: [
                        imageUrl.isNotEmpty
                            ? Image.network(imageUrl,
                                height: 220,
                                width: double.infinity,
                                fit: BoxFit.cover,
                                errorBuilder: (_, __, ___) => _projectImagePlaceholder())
                            : _projectImagePlaceholder(),
                        Positioned(
                          top: 16,
                          left: 16,
                          child: Container(
                            padding: const EdgeInsets.symmetric(
                                horizontal: 12, vertical: 6),
                            decoration: BoxDecoration(
                                color: primaryBlue,
                                borderRadius: BorderRadius.circular(20)),
                            child: const Text('SOCIAL HOUSING',
                                style: TextStyle(
                                    color: Colors.white,
                                    fontSize: 10,
                                    fontWeight: FontWeight.bold,
                                    letterSpacing: 1.2)),
                          ),
                        ),
                      ],
                    ),
                    Padding(
                      padding: const EdgeInsets.all(20),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(title,
                              style: const TextStyle(
                                  fontWeight: FontWeight.bold,
                                  fontSize: 18,
                                  color: darkText)),
                          Text(location,
                              style: TextStyle(
                                  color: Colors.grey.shade600, fontSize: 12)),
                          const SizedBox(height: 16),
                          Row(children: [
                            _buildPropertyDetailChip(price),
                          ]),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          );
        },
      ),
    );
  }

  Widget _projectImagePlaceholder() => Container(
        height: 220,
        width: double.infinity,
        color: Colors.grey.shade100,
        child: Icon(Icons.apartment_rounded,
            size: 60, color: Colors.grey.shade300),
      );

  Widget _buildPropertyDetailChip(String detail) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
      decoration: BoxDecoration(color: Colors.blue.shade50, borderRadius: BorderRadius.circular(8)),
      child: Text(detail, style: const TextStyle(color: primaryBlue, fontSize: 11, fontWeight: FontWeight.w600)),
    );
  }

  Widget _buildFloatingNavBar() {
    return Positioned(
      bottom: 40,
      left: 30,
      right: 30,
      child: Container(
        height: 70,
        decoration: BoxDecoration(
          color: darkText,
          borderRadius: BorderRadius.circular(35),
          boxShadow: [
            BoxShadow(color: Colors.black.withValues(alpha: 0.3), blurRadius: 20, offset: const Offset(0, 10)),
          ],
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.spaceEvenly,
          children: [
            _navIcon(Icons.grid_view, "Home", true, () {}),
            _navIcon(Icons.business, "Projects", false, () {
              Navigator.push(context, MaterialPageRoute(builder: (context) => const ProjectsPage()));
            }),
            _navIcon(Icons.search, "Search", false, () {
              Navigator.push(context, MaterialPageRoute(builder: (context) => const SearchPage()));
            }),
            _navIcon(Icons.person_outline, "Profile", false, () {
              Navigator.push(context, MaterialPageRoute(builder: (context) => const ProfilePage()));
            }),
          ],
        ),
      ),
    );
  }

  Widget _navIcon(IconData icon, String label, bool isActive, VoidCallback onTap) {
    return Tooltip(
      message: label,
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(35),
        child: Padding(
          padding: const EdgeInsets.all(12.0),
          child: Icon(icon, color: isActive ? primaryBlue : Colors.white60, size: 28),
        ),
      ),
    );
  }
}