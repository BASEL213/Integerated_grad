import 'package:flutter/material.dart';

class PropertyDetailsPage extends StatelessWidget {
  final Map<String, String> property;

  const PropertyDetailsPage({super.key, required this.property});

  static const Color primaryBlue = Color(0xFF1E88E5);
  static const Color darkText = Color(0xFF263238);

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.white,
      body: Stack(
        children: [
          // 1. Property Image Header
          SingleChildScrollView(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Stack(
                  children: [
                    Image.network(
                      property['image']!,
                      height: 400,
                      width: double.infinity,
                      fit: BoxFit.cover,
                    ),
                    SafeArea(
                      child: Padding(
                        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                        child: CircleAvatar(
                          backgroundColor: Colors.white.withValues(alpha: 0.9),
                          child: IconButton(
                            icon: const Icon(Icons.arrow_back_ios_new, color: darkText, size: 20),
                            onPressed: () => Navigator.pop(context),
                          ),
                        ),
                      ),
                    ),
                  ],
                ),
                Padding(
                  padding: const EdgeInsets.all(24.0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        mainAxisAlignment: MainAxisAlignment.spaceBetween,
                        children: [
                          Text(property['title']!,
                              style: const TextStyle(fontSize: 24, fontWeight: FontWeight.bold, color: darkText)),
                          Text(property['price']!,
                              style: const TextStyle(fontSize: 22, fontWeight: FontWeight.bold, color: primaryBlue)),
                        ],
                      ),
                      const SizedBox(height: 8),
                      Row(
                        children: [
                          const Icon(Icons.location_on, color: Colors.grey, size: 16),
                          const SizedBox(width: 4),
                          Text(property['location']!, style: const TextStyle(color: Colors.grey)),
                        ],
                      ),
                      const SizedBox(height: 24),
                      const Text("Description",
                          style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: darkText)),
                      const SizedBox(height: 12),
                      const Text(
                        "This premium property offers a modern living experience with high-end finishes and breathtaking views. Located in a prime district with easy access to all major services.",
                        style: TextStyle(color: Colors.blueGrey, height: 1.5),
                      ),
                      const SizedBox(height: 32),
                      const Text("Amenities",
                          style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: darkText)),
                      const SizedBox(height: 16),
                      _buildAmenitiesGrid(),
                      const SizedBox(height: 100), // Space for bottom button
                    ],
                  ),
                ),
              ],
            ),
          ),
          // 2. Bottom Action Bar
          _buildBottomAction(),
        ],
      ),
    );
  }

  Widget _buildAmenitiesGrid() {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        _amenityIcon(Icons.pool, "Pool"),
        _amenityIcon(Icons.fitness_center, "Gym"),
        _amenityIcon(Icons.wifi, "Wi-Fi"),
        _amenityIcon(Icons.local_parking, "Parking"),
      ],
    );
  }

  Widget _amenityIcon(IconData icon, String label) {
    return Column(
      children: [
        Container(
          padding: const EdgeInsets.all(12),
          decoration: BoxDecoration(
            color: const Color(0xFFF1F5F9),
            borderRadius: BorderRadius.circular(15),
          ),
          child: Icon(icon, color: primaryBlue),
        ),
        const SizedBox(height: 8),
        Text(label, style: const TextStyle(fontSize: 12, color: darkText)),
      ],
    );
  }

  Widget _buildBottomAction() {
    return Align(
      alignment: Alignment.bottomCenter,
      child: Container(
        padding: const EdgeInsets.all(24),
        decoration: BoxDecoration(
          color: Colors.white,
          boxShadow: [BoxShadow(color: Colors.black.withValues(alpha: 0.05), blurRadius: 20, offset: const Offset(0, -5))],
        ),
        child: ElevatedButton(
          onPressed: () {},
          style: ElevatedButton.styleFrom(
            backgroundColor: primaryBlue,
            minimumSize: const Size(double.infinity, 56),
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          ),
          child: const Text("Contact Agent", style: TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
        ),
      ),
    );
  }
}