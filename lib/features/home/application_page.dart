import 'package:flutter/material.dart';
import 'documents_vault_screen.dart';

class ApplicationPage extends StatefulWidget {
  const ApplicationPage({super.key});

  @override
  State<ApplicationPage> createState() => _ApplicationPageState();
}

class _ApplicationPageState extends State<ApplicationPage> {
  int _currentStep = 0;
  final _formKey = GlobalKey<FormState>();

  // --- Controllers ---
  final TextEditingController _fullNameController = TextEditingController();
  final TextEditingController _idController = TextEditingController();
  final TextEditingController _emailController = TextEditingController();
  final TextEditingController _phoneController = TextEditingController();
  final TextEditingController _incomeController = TextEditingController();
  final TextEditingController _familySizeController = TextEditingController();
  final TextEditingController _housingDescController = TextEditingController();
  final TextEditingController _requirementsController = TextEditingController();

  // --- Dropdown Variables ---
  String? selectedProject;
  String? selectedUnitType;
  String? selectedFloor;
  String? selectedPaymentMethod;

  static const Color primaryBlue = Color(0xFF1E88E5);
  static const Color darkText = Color(0xFF263238);

  // --- Functions ---

  void _handleNavigation() {
    if (_currentStep < 3) {
      if (_currentStep == 0) {
        if (_formKey.currentState!.validate()) {
          setState(() => _currentStep++);
        }
      } else {
        setState(() => _currentStep++);
      }
    } else {
      _submitToBackend();
    }
  }

  // الدالة المعدلة لحل مشكلة Context across async gaps
  Future<void> _submitToBackend() async {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => const Center(child: CircularProgressIndicator(color: primaryBlue)),
    );

    // محاكاة الاتصال بالـ API أو الباك إند
    await Future.delayed(const Duration(seconds: 2));

    // الحل: التأكد أن الـ Widget مازال موجوداً قبل استخدام Navigator
    if (!mounted) return;

    Navigator.pop(context); // إغلاق الـ Loading
    _showSuccessDialog();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF8FAFC),
      appBar: AppBar(
        title: const Text("Housing Application", style: TextStyle(fontWeight: FontWeight.bold, fontSize: 18)),
        backgroundColor: Colors.white,
        foregroundColor: darkText,
        elevation: 0.5,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_new, size: 20),
          onPressed: () => Navigator.pop(context),
        ),
      ),
      body: Column(
        children: [
          _buildStepTracker(),
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: Form(key: _formKey, child: _buildCurrentStepContent()),
            ),
          ),
          _buildBottomActions(),
        ],
      ),
    );
  }

  Widget _buildCurrentStepContent() {
    switch (_currentStep) {
      case 0: return _buildPersonalInfoStep();
      case 1: return _buildProjectInfoStep();
      case 2: return _buildFinancialAndHousingStep();
      case 3: return _buildDocumentStep();
      default: return const SizedBox();
    }
  }

  // --- Steps Build Methods ---

  Widget _buildPersonalInfoStep() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _sectionHeader(Icons.person_outline, "Personal Information"),
        const SizedBox(height: 20),
        _buildInputField("Full Name", Icons.person, _fullNameController),
        _buildInputField("National ID", Icons.badge_outlined, _idController, isNumber: true),
        _buildInputField("Email Address", Icons.email_outlined, _emailController),
        _buildInputField("Phone Number", Icons.phone_android, _phoneController, isNumber: true),
      ],
    );
  }

  Widget _buildProjectInfoStep() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _sectionHeader(Icons.apartment_rounded, "Project Details"),
        const SizedBox(height: 20),
        _buildDropdown("Preferred Project", ["New Cairo Area", "Zayed Towers", "October Gardens"], (v) => selectedProject = v),
        _buildDropdown("Unit Type", ["Studio", "2-Bedroom Apartment", "3-Bedroom Apartment"], (v) => selectedUnitType = v),
        _buildDropdown("Preferred Floor", ["Ground Floor", "Typical Floor", "Roof Floor"], (v) => selectedFloor = v),
        _buildDropdown("Payment Plan", ["Cash (Full)", "Installments (5 Years)", "Mortgage (20 Years)"], (v) => selectedPaymentMethod = v),
      ],
    );
  }

  Widget _buildFinancialAndHousingStep() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _sectionHeader(Icons.monetization_on_outlined, "Financial Status"),
        const SizedBox(height: 20),
        Row(
          children: [
            Expanded(child: _buildInputField("Monthly Income (EGP)", Icons.wallet, _incomeController, isNumber: true)),
            const SizedBox(width: 15),
            Expanded(child: _buildInputField("Family Size", Icons.group_outlined, _familySizeController, isNumber: true)),
          ],
        ),
        const Divider(height: 40),
        _sectionHeader(Icons.home_work_outlined, "Current Housing Context"),
        const SizedBox(height: 20),
        _buildInputField("Briefly describe current residence", Icons.info_outline, _housingDescController, isLongText: true),
        _buildInputField("Any special health/social requirements", Icons.star_border, _requirementsController, isLongText: true),
      ],
    );
  }

  Widget _buildDocumentStep() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        _sectionHeader(Icons.cloud_upload_outlined, "Verification Documents"),
        const SizedBox(height: 10),
        const Text("Use your vault for faster submission.", style: TextStyle(color: Colors.grey, fontSize: 13)),
        const SizedBox(height: 25),
        _buildDocPicker("National ID Copy (Front/Back)"),
        _buildDocPicker("Latest Income Certificate"),
        _buildDocPicker("Family Status Document"),
      ],
    );
  }

  // --- UI Components ---

  Widget _sectionHeader(IconData icon, String title) {
    return Row(children: [
      Icon(icon, color: primaryBlue, size: 24),
      const SizedBox(width: 10),
      Text(title, style: const TextStyle(fontSize: 18, fontWeight: FontWeight.bold, color: darkText)),
    ]);
  }

  Widget _buildInputField(String label, IconData icon, TextEditingController controller, {bool isNumber = false, bool isLongText = false}) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: TextFormField(
        controller: controller,
        maxLines: isLongText ? 3 : 1,
        keyboardType: isNumber ? TextInputType.number : TextInputType.text,
        decoration: InputDecoration(
          labelText: label,
          prefixIcon: Icon(icon, color: Colors.grey.shade400, size: 20),
          filled: true,
          fillColor: Colors.white,
          enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide(color: Colors.grey.shade200)),
          focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: primaryBlue, width: 1.5)),
        ),
      ),
    );
  }

  Widget _buildDropdown(String label, List<String> items, Function(String?) onChanged) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: DropdownButtonFormField<String>(
        decoration: InputDecoration(
          labelText: label,
          filled: true,
          fillColor: Colors.white,
          enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide(color: Colors.grey.shade200)),
          focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: const BorderSide(color: primaryBlue)),
        ),
        items: items.map((e) => DropdownMenuItem(value: e, child: Text(e))).toList(),
        onChanged: onChanged,
      ),
    );
  }

  Widget _buildDocPicker(String title) {
    return Container(
      margin: const EdgeInsets.only(bottom: 15),
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(15),
        border: Border.all(color: Colors.grey.shade100),
      ),
      child: Row(
        children: [
          const Icon(Icons.file_present_rounded, color: primaryBlue),
          const SizedBox(width: 15),
          Expanded(child: Text(title, style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w500))),
          ElevatedButton(
            onPressed: () => _showUploadOptions(title),
            style: ElevatedButton.styleFrom(backgroundColor: primaryBlue, shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(8)), elevation: 0),
            child: const Text("Select", style: TextStyle(color: Colors.white)),
          ),
        ],
      ),
    );
  }

  void _showUploadOptions(String docTitle) {
    showModalBottomSheet(
      context: context,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.vertical(top: Radius.circular(25))),
      builder: (context) => Padding(
        padding: const EdgeInsets.all(30),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Text("How to add this document?", style: TextStyle(fontSize: 18, fontWeight: FontWeight.bold)),
            const SizedBox(height: 20),
            ListTile(
              leading: const Icon(Icons.upload_file, color: Colors.green),
              title: const Text("Upload from Device"),
              onTap: () => Navigator.pop(context),
            ),
            ListTile(
              leading: const Icon(Icons.security_outlined, color: primaryBlue),
              title: const Text("Select from Documents Vault"),
              onTap: () {
                Navigator.pop(context);
                Navigator.push(context, MaterialPageRoute(builder: (context) => const DocumentsVaultScreen()));
              },
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildStepTracker() {
    return Container(
      color: Colors.white,
      padding: const EdgeInsets.symmetric(vertical: 20),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.center,
        children: List.generate(4, (index) => _buildStepItem(index)),
      ),
    );
  }

  Widget _buildStepItem(int index) {
    bool isActive = _currentStep >= index;
    bool isCompleted = _currentStep > index;
    return Row(
      children: [
        Container(
          width: 28, height: 28,
          decoration: BoxDecoration(color: isCompleted ? Colors.green : (isActive ? primaryBlue : Colors.grey.shade200), shape: BoxShape.circle),
          child: Center(child: isCompleted ? const Icon(Icons.check, color: Colors.white, size: 16) : Text("${index + 1}", style: TextStyle(color: isActive ? Colors.white : Colors.grey, fontWeight: FontWeight.bold))),
        ),
        if (index < 3) Container(width: 40, height: 2, color: _currentStep > index ? Colors.green : Colors.grey.shade200),
      ],
    );
  }

  Widget _buildBottomActions() {
    return Container(
      padding: const EdgeInsets.all(24),
      decoration: BoxDecoration(color: Colors.white, border: Border(top: BorderSide(color: Colors.grey.shade100))),
      child: Row(
        children: [
          if (_currentStep > 0)
            Expanded(child: OutlinedButton(onPressed: () => setState(() => _currentStep--), style: OutlinedButton.styleFrom(minimumSize: const Size(0, 55)), child: const Text("Back"))),
          if (_currentStep > 0) const SizedBox(width: 16),
          Expanded(
            child: ElevatedButton(
              onPressed: _handleNavigation,
              style: ElevatedButton.styleFrom(backgroundColor: primaryBlue, minimumSize: const Size(0, 55), shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12))),
              child: Text(_currentStep == 3 ? "Submit Application" : "Continue", style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold)),
            ),
          ),
        ],
      ),
    );
  }

  void _showSuccessDialog() {
    showDialog(
      context: context,
      barrierDismissible: false,
      builder: (context) => AlertDialog(
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.check_circle_rounded, color: Colors.green, size: 80),
            const SizedBox(height: 20),
            const Text("Success!", style: TextStyle(fontSize: 22, fontWeight: FontWeight.bold)),
            const SizedBox(height: 10),
            const Text("Your application has been submitted to the housing department.", textAlign: TextAlign.center),
            const SizedBox(height: 30),
            SizedBox(width: double.infinity, child: ElevatedButton(onPressed: () {
              Navigator.pop(context); // إغلاق الديالوج
              Navigator.pop(context); // العودة للشاشة السابقة
            }, child: const Text("Done"))),
          ],
        ),
      ),
    );
  }
}