import 'package:flutter/material.dart';

class SearchPage extends StatelessWidget {
  const SearchPage({super.key});

  static const Color primaryBlue = Color(0xFF1E88E5);
  static const Color darkText = Color(0xFF263238);

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
        title: TextField(
          autofocus: true,
          decoration: InputDecoration(
            hintText: "Search for units, locations...",
            hintStyle: TextStyle(color: Colors.grey.shade400),
            border: InputBorder.none,
          ),
        ),
      ),
      body: Padding(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text("Recent Searches",
                style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18, color: darkText)),
            const SizedBox(height: 16),
            _buildSearchTag("Apartments in New Cairo"),
            _buildSearchTag("Social Housing Project 12"),
            _buildSearchTag("Middle class units Downtown"),
          ],
        ),
      ),
    );
  }

  Widget _buildSearchTag(String text) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        children: [
          const Icon(Icons.history, color: Colors.grey, size: 20),
          const SizedBox(width: 12),
          Text(text, style: const TextStyle(color: Colors.grey, fontSize: 15)),
          const Spacer(),
          const Icon(Icons.north_west, color: Colors.grey, size: 16),
        ],
      ),
    );
  }
}