import 'package:flutter/material.dart';
import 'package:dio/dio.dart';
import 'dart:developer' as developer;

class ProjectsPage extends StatefulWidget {
  const ProjectsPage({super.key});

  @override
  State<ProjectsPage> createState() => _ProjectsPageState();
}

class _ProjectsPageState extends State<ProjectsPage> {
  static const Color primaryBlue = Color(0xFF1E88E5);
  static const Color darkText = Color(0xFF263238);

  final Dio _dio = Dio();
  List _projects = [];
  bool _isLoading = true;
  String _errorMessage = "";

  @override
  void initState() {
    super.initState();
    _fetchProjects();
  }

  Future<void> _fetchProjects() async {
    try {
      setState(() {
        _isLoading = true;
        _errorMessage = "";
      });

      // الرابط باستخدام الـ IP بتاعك لضمان الاتصال بالسيرفر من الموبايل
      final response = await _dio.get('http://192.168.1.8:5000/api/projects');

      if (response.statusCode == 200) {
        setState(() {
          // التعامل مع الـ Data سواء كانت مبعوثة مباشرة أو جوه key اسمه data
          if (response.data is List) {
            _projects = response.data;
          } else {
            _projects = response.data['data'] ?? [];
          }
          _isLoading = false;
        });
      }
    } catch (e) {
      setState(() {
        _isLoading = false;
        _errorMessage = "Connection Error. Make sure your Laptop and Mobile are on the same Wi-Fi!";
      });
      developer.log("Error fetching data", error: e);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF8FAFC),
      appBar: AppBar(
        backgroundColor: Colors.transparent,
        elevation: 0,
        centerTitle: true,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_new, color: darkText, size: 20),
          onPressed: () => Navigator.pop(context),
        ),
        title: const Text("Major Projects",
            style: TextStyle(color: darkText, fontWeight: FontWeight.bold, fontSize: 18)),
        actions: [
          IconButton(
            onPressed: _fetchProjects,
            icon: const Icon(Icons.refresh, color: primaryBlue),
          )
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator(color: primaryBlue))
          : _errorMessage.isNotEmpty
          ? Center(child: Column(
        mainAxisAlignment: MainAxisAlignment.center,
        children: [
          const Icon(Icons.wifi_off, size: 50, color: Colors.grey),
          const SizedBox(height: 16),
          Text(_errorMessage, textAlign: TextAlign.center),
          TextButton(onPressed: _fetchProjects, child: const Text("Retry"))
        ],
      ))
          : ListView.builder(
        padding: const EdgeInsets.all(24),
        itemCount: _projects.length,
        itemBuilder: (context, index) {
          final project = _projects[index];

          // --- استخراج البيانات بشكل مرن ليطابق ما يرسله الويب ---
          String name = project['name'] ?? "No Name";

          // التعامل مع الـ location سواء كان String أو Object
          String locationText = "";
          if (project['location'] is String) {
            locationText = project['location'];
          } else if (project['location'] is Map) {
            locationText = project['location']['city'] ?? "Unknown City";
          } else {
            locationText = "Location N/A";
          }

          // قراءة الوحدات والسعر من الـ Root مباشرة (كما في الويب)
          int available = project['availableUnits'] ?? 0;
          String price = project['priceRange'] ?? "N/A";
          String status = project['status'] ?? "active";

          return Padding(
            padding: const EdgeInsets.only(bottom: 20),
            child: _buildProjectCard(
              name,
              locationText,
              "$available Units Left",
              price,
              status.toUpperCase(),
            ),
          );
        },
      ),
    );
  }

  Widget _buildProjectCard(String name, String location, String units, String price, String badge) {
    return Container(
      height: 260,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(28),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withOpacity(0.1),
            blurRadius: 10,
            offset: const Offset(0, 5),
          )
        ],
        image: const DecorationImage(
          image: NetworkImage("https://images.unsplash.com/photo-1486406146926-c627a92ad1ab?q=80&w=600"),
          fit: BoxFit.cover,
        ),
      ),
      child: Container(
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(28),
          gradient: LinearGradient(
            begin: Alignment.bottomCenter,
            end: Alignment.topCenter,
            colors: [Colors.black.withOpacity(0.85), Colors.transparent],
          ),
        ),
        padding: const EdgeInsets.all(20),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.end,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                  decoration: BoxDecoration(
                      color: badge == "ACTIVE" ? Colors.green : Colors.orange,
                      borderRadius: BorderRadius.circular(8)
                  ),
                  child: Text(badge, style: const TextStyle(color: Colors.white, fontSize: 10, fontWeight: FontWeight.bold)),
                ),
                Text(price, style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 16)),
              ],
            ),
            const SizedBox(height: 10),
            Text(name, style: const TextStyle(color: Colors.white, fontSize: 22, fontWeight: FontWeight.bold)),
            const SizedBox(height: 5),
            Row(
              children: [
                const Icon(Icons.location_on, color: Colors.white70, size: 16),
                const SizedBox(width: 4),
                Expanded(child: Text(location, style: const TextStyle(color: Colors.white70, fontSize: 13), overflow: TextOverflow.ellipsis)),
                Text(units, style: const TextStyle(color: Colors.orangeAccent, fontSize: 13, fontWeight: FontWeight.w600)),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
