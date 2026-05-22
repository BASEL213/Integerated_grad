import 'package:flutter/material.dart';
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
  static const Color darkBlue = Color(0xFF1565C0);
  static const Color premiumBackground = Color(0xFFF8FAFC);
  static const Color darkText = Color(0xFF263238);

  final List<Map<String, String>> properties = [
    {
      'title': 'The Grand Residence',
      'location': 'New Cairo, Egypt',
      'price': '\$ 3,450',
      'beds': '4 Bd',
      'baths': '3 Ba',
      'sqft': '320 SqFt',
      'image': 'https://images.unsplash.com/photo-1600585154340-be6161a56a0c?q=80&w=600',
    },
    {
      'title': 'The Urban Loft',
      'location': 'Downtown Cairo, Egypt',
      'price': '\$ 2,100',
      'beds': '2 Bd',
      'baths': '1 Ba',
      'sqft': '180 SqFt',
      'image': 'https://images.unsplash.com/photo-1512917774080-9991f1c4c750?q=80&w=600',
    },
  ];

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
          const Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text("Hi Ahmed", style: TextStyle(color: Colors.grey, fontSize: 16)),
              Text("Good Morning,",
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
                  Navigator.push(context, MaterialPageRoute(builder: (context) => const StatusPage()));
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
    return SizedBox(
      height: 380,
      child: PageView.builder(
        controller: PageController(viewportFraction: 0.9),
        itemCount: properties.length,
        itemBuilder: (context, index) {
          final data = properties[index];
          return Tooltip(
            message: "Click to view details",
            child: InkWell(
              onTap: () {
                Navigator.push(
                  context,
                  MaterialPageRoute(builder: (context) => PropertyDetailsPage(property: data)),
                );
              },
              borderRadius: BorderRadius.circular(32),
              child: Container(
                margin: const EdgeInsets.only(right: 20, bottom: 20),
                decoration: BoxDecoration(
                  color: Colors.white,
                  borderRadius: BorderRadius.circular(32),
                  boxShadow: [
                    BoxShadow(color: Colors.black.withValues(alpha: 0.04), blurRadius: 20, offset: const Offset(0, 10)),
                  ],
                ),
                child: ClipRRect(
                  borderRadius: BorderRadius.circular(32),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Stack(
                        children: [
                          Image.network(data['image']!, height: 220, width: double.infinity, fit: BoxFit.cover),
                          Positioned(
                            top: 16,
                            left: 16,
                            child: Container(
                              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
                              decoration: BoxDecoration(color: primaryBlue, borderRadius: BorderRadius.circular(20)),
                              child: const Text("FOR SALE",
                                  style: TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.bold, letterSpacing: 1.2)),
                            ),
                          ),
                        ],
                      ),
                      Padding(
                        padding: const EdgeInsets.all(20),
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(data['title']!,
                                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 18, color: darkText)),
                            Text(data['location']!,
                                style: TextStyle(color: Colors.grey.shade600, fontSize: 12)),
                            const SizedBox(height: 16),
                            Row(
                              children: [
                                _buildPropertyDetailChip(data['beds']!),
                                const SizedBox(width: 8),
                                _buildPropertyDetailChip(data['baths']!),
                                const SizedBox(width: 8),
                                _buildPropertyDetailChip(data['sqft']!),
                              ],
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                ),
              ),
            ),
          );
        },
      ),
    );
  }

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