import 'package:dio/dio.dart';
import 'package:flutter/foundation.dart' show kIsWeb;
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:image_picker/image_picker.dart';

// ─── Constants ───────────────────────────────────────────────────────────────

const Color _primary  = Color(0xFF1E88E5);
const Color _dark     = Color(0xFF1565C0);
const Color _bg       = Color(0xFFF8FAFC);
const Color _textDark = Color(0xFF263238);
const Color _textMid  = Color(0xFF455A64);

/// Web (Chrome): talks to localhost directly.
/// Android emulator: 10.0.2.2 maps to the host machine's localhost.
/// Physical device: change to your machine's LAN IP, e.g. 192.168.1.x
String get _apiBase =>
    kIsWeb ? 'http://localhost:5001' : 'http://10.0.2.2:5001';

// ─── State enum ──────────────────────────────────────────────────────────────

enum _ScanState { options, processing, results, failed }

// ─── Main screen ─────────────────────────────────────────────────────────────

/// Navigate to this screen and await the result.
/// Returns `Map<String, String>?` on success, `null` on cancel/error.
///
/// Keys returned:
///   'name', 'nationalId', 'dateOfBirth', 'address',
///   'districtAndGovernorate', 'cardNumber'
class NIDScanScreen extends StatefulWidget {
  const NIDScanScreen({super.key});

  @override
  State<NIDScanScreen> createState() => _NIDScanScreenState();
}

class _NIDScanScreenState extends State<NIDScanScreen> {
  // ── Page state ───────────────────────────────────────────────────────────
  _ScanState _state       = _ScanState.options;
  String     _errorMessage = '';

  // ── Result field controllers ──────────────────────────────────────────────
  late final TextEditingController _nameCtrl;
  late final TextEditingController _idCtrl;
  late final TextEditingController _dobCtrl;
  late final TextEditingController _addressCtrl;
  late final TextEditingController _districtCtrl;
  late final TextEditingController _cardNumCtrl;
  int _extractedCount = 0;

  // ─────────────────────────────────────────────────────────────────────────
  @override
  void initState() {
    super.initState();
    _nameCtrl     = TextEditingController();
    _idCtrl       = TextEditingController();
    _dobCtrl      = TextEditingController();
    _addressCtrl  = TextEditingController();
    _districtCtrl = TextEditingController();
    _cardNumCtrl  = TextEditingController();
  }

  @override
  void dispose() {
    _nameCtrl.dispose();
    _idCtrl.dispose();
    _dobCtrl.dispose();
    _addressCtrl.dispose();
    _districtCtrl.dispose();
    _cardNumCtrl.dispose();
    super.dispose();
  }

  // ─── Image acquisition (gallery only) ────────────────────────────────────

  Future<void> _pickFromGallery() async {
    try {
      final picker = ImagePicker();
      final picked = await picker.pickImage(
        source: ImageSource.gallery,
        imageQuality: 90,
      );
      if (picked != null && mounted) await _processImage(picked.path);
    } catch (e) {
      _setError('Could not open gallery. Please try again.\n$e');
    }
  }

  // ─── OCR pipeline ────────────────────────────────────────────────────────

  Future<void> _processImage(String imagePath) async {
    if (!mounted) return;
    setState(() => _state = _ScanState.processing);

    try {
      final data = await _callOcrApi(imagePath);

      _nameCtrl.text     = data['الاسم بالكامل']      as String? ?? '';
      _idCtrl.text       = data['الرقم القومي']       as String? ?? '';
      _dobCtrl.text      = data['تاريخ الميلاد']     as String? ?? '';
      _addressCtrl.text  = data['العنوان بالكامل']    as String? ?? '';
      _districtCtrl.text = data['المنطقة والمحافظة'] as String? ?? '';
      _cardNumCtrl.text  = data['رقم البطاقة']       as String? ?? '';

      _extractedCount = [
        _nameCtrl.text,
        _idCtrl.text,
        _dobCtrl.text,
        _addressCtrl.text,
        _districtCtrl.text,
        _cardNumCtrl.text,
      ].where((v) => v.isNotEmpty).length;

      if (!mounted) return;
      if (_extractedCount == 0) {
        _setError(
          'Could not read any fields from the image.\n'
          'Ensure the card is well-lit, in focus, and fully visible.',
        );
      } else {
        setState(() => _state = _ScanState.results);
      }
    } on DioException catch (e) {
      final serverMsg = e.response?.data is Map
          ? (e.response!.data['error'] as String? ?? '')
          : '';
      final msg = switch (e.type) {
        DioExceptionType.connectionTimeout ||
        DioExceptionType.sendTimeout ||
        DioExceptionType.receiveTimeout =>
          'Request timed out.\nThe OCR server may still be loading — try again in a moment.',
        DioExceptionType.connectionError ||
        DioExceptionType.unknown =>
          'Cannot reach the OCR server.\nMake sure it is running on port 5001.',
        _ =>
          'Server error (${e.response?.statusCode ?? "?"}).'
          '${serverMsg.isNotEmpty ? "\n$serverMsg" : ""}',
      };
      _setError(msg);
    } catch (e) {
      _setError('Unexpected error: $e');
    }
  }

  Future<Map<String, dynamic>> _callOcrApi(String imagePath) async {
    final dio = Dio(BaseOptions(
      connectTimeout: const Duration(seconds: 20),
      sendTimeout:    const Duration(seconds: 60),
      receiveTimeout: const Duration(minutes: 5), // OCR takes ~3-4 min on CPU
    ));

    // XFile.readAsBytes() works on mobile (real path) and web (blob URL).
    final bytes    = await XFile(imagePath).readAsBytes();
    final formData = FormData.fromMap({
      'image': MultipartFile.fromBytes(bytes, filename: 'nid.jpg'),
    });

    final response = await dio.post('$_apiBase/ocr/extract', data: formData);
    if (response.statusCode == 200 && response.data['success'] == true) {
      return response.data['data'] as Map<String, dynamic>;
    }
    throw Exception(response.data['error'] ?? 'Unknown server error');
  }

  // ─── Actions ─────────────────────────────────────────────────────────────

  void _setError(String msg) {
    if (!mounted) return;
    setState(() {
      _errorMessage = msg;
      _state = _ScanState.failed;
    });
  }

  void _backToOptions() {
    setState(() {
      _state        = _ScanState.options;
      _errorMessage = '';
    });
  }

  void _confirm() {
    Navigator.pop(context, {
      'name':                    _nameCtrl.text,
      'nationalId':              _idCtrl.text,
      'dateOfBirth':             _dobCtrl.text,
      'address':                 _addressCtrl.text,
      'districtAndGovernorate':  _districtCtrl.text,
      'cardNumber':              _cardNumCtrl.text,
    });
  }

  // ═══════════════════════════════════════════════════════════════════════════
  // BUILD
  // ═══════════════════════════════════════════════════════════════════════════

  @override
  Widget build(BuildContext context) {
    return switch (_state) {
      _ScanState.options    => _buildOptionsPage(),
      _ScanState.processing => _buildProcessingPage(),
      _ScanState.results    => _buildResultsPage(),
      _ScanState.failed     => _buildErrorPage(),
    };
  }

  // ─── Options page ─────────────────────────────────────────────────────────

  Widget _buildOptionsPage() {
    return Scaffold(
      backgroundColor: _bg,
      body: Column(
        children: [
          _buildHeader(
            icon:     Icons.credit_card_rounded,
            title:    'Scan Your NID',
            subtitle: 'Auto-fill your details from your National ID card',
          ),
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 28),
              child: Column(
                children: [
                  _buildInfoBanner(),
                  const SizedBox(height: 28),

                  // ── Upload from gallery — the only capture method ──────
                  _buildUploadButton(),

                  const SizedBox(height: 28),
                  _buildFieldsPreview(),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildHeader({
    required IconData icon,
    required String   title,
    required String   subtitle,
  }) {
    return Container(
      width: double.infinity,
      decoration: const BoxDecoration(
        gradient: LinearGradient(colors: [_primary, _dark]),
        borderRadius: BorderRadius.only(
          bottomLeft:  Radius.circular(60),
          bottomRight: Radius.circular(30),
        ),
      ),
      child: SafeArea(
        bottom: false,
        child: Padding(
          padding: const EdgeInsets.fromLTRB(24, 12, 24, 32),
          child: Row(
            children: [
              IconButton(
                icon: const Icon(Icons.arrow_back_ios_new,
                    color: Colors.white, size: 20),
                onPressed: () => Navigator.pop(context),
              ),
              const SizedBox(width: 8),
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: Colors.white.withValues(alpha: 0.2),
                  borderRadius: BorderRadius.circular(14),
                ),
                child: Icon(icon, color: Colors.white, size: 28),
              ),
              const SizedBox(width: 16),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title,
                        style: GoogleFonts.poppins(
                          fontSize:   20,
                          fontWeight: FontWeight.bold,
                          color:      Colors.white,
                        )),
                    Text(subtitle,
                        style: GoogleFonts.poppins(
                          fontSize: 12,
                          color:    Colors.white70,
                        )),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildInfoBanner() {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color:        _primary.withValues(alpha: 0.07),
        borderRadius: BorderRadius.circular(14),
        border:       Border.all(color: _primary.withValues(alpha: 0.2)),
      ),
      child: Row(
        children: [
          const Icon(Icons.auto_awesome_rounded, color: _primary, size: 22),
          const SizedBox(width: 12),
          Expanded(
            child: Text(
              'OCR will automatically extract your name, national ID, '
              'date of birth, address, and more.',
              style: GoogleFonts.poppins(fontSize: 12, color: _textMid),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildUploadButton() {
    return GestureDetector(
      onTap: _pickFromGallery,
      child: Container(
        width:   double.infinity,
        padding: const EdgeInsets.all(24),
        decoration: BoxDecoration(
          color:         _primary,
          borderRadius:  BorderRadius.circular(20),
          boxShadow: [
            BoxShadow(
              color:      _primary.withValues(alpha: 0.35),
              blurRadius: 18,
              offset:     const Offset(0, 8),
            ),
          ],
        ),
        child: Column(
          children: [
            Container(
              padding:    const EdgeInsets.all(18),
              decoration: BoxDecoration(
                color:        Colors.white.withValues(alpha: 0.2),
                borderRadius: BorderRadius.circular(18),
              ),
              child: const Icon(Icons.photo_library_rounded,
                  color: Colors.white, size: 40),
            ),
            const SizedBox(height: 16),
            Text('Upload NID Image',
                style: GoogleFonts.poppins(
                  fontWeight: FontWeight.bold,
                  fontSize:   18,
                  color:      Colors.white,
                )),
            const SizedBox(height: 6),
            Text('Choose a clear photo of your ID card from your gallery',
                textAlign: TextAlign.center,
                style: GoogleFonts.poppins(
                  fontSize: 13,
                  color:    Colors.white70,
                )),
          ],
        ),
      ),
    );
  }

  Widget _buildFieldsPreview() {
    final fields = [
      (Icons.person_outline,       'Full Name'),
      (Icons.badge_outlined,       'National ID (14 digits)'),
      (Icons.cake_outlined,        'Date of Birth'),
      (Icons.location_on_outlined, 'Street Address'),
      (Icons.map_outlined,         'District & Governorate'),
      (Icons.credit_card_outlined, 'Card Serial Number'),
    ];
    return Container(
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color:        Colors.white,
        borderRadius: BorderRadius.circular(18),
        boxShadow: [
          BoxShadow(
            color:      Colors.black.withValues(alpha: 0.04),
            blurRadius: 12,
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text('Fields that will be extracted',
              style: GoogleFonts.poppins(
                fontWeight: FontWeight.w600,
                fontSize:   13,
                color:      _textDark,
              )),
          const SizedBox(height: 12),
          ...fields.map((f) => Padding(
                padding: const EdgeInsets.symmetric(vertical: 5),
                child: Row(
                  children: [
                    Icon(f.$1, size: 16, color: _primary),
                    const SizedBox(width: 10),
                    Text(f.$2,
                        style: GoogleFonts.poppins(
                          fontSize: 13,
                          color:    _textMid,
                        )),
                  ],
                ),
              )),
        ],
      ),
    );
  }

  // ─── Processing page ──────────────────────────────────────────────────────

  Widget _buildProcessingPage() {
    return Scaffold(
      backgroundColor: _bg,
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              width:  96,
              height: 96,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: _primary.withValues(alpha: 0.1),
              ),
              child: const Padding(
                padding: EdgeInsets.all(24),
                child:   CircularProgressIndicator(
                  color:       _primary,
                  strokeWidth: 3,
                ),
              ),
            ),
            const SizedBox(height: 28),
            Text('Reading your ID card…',
                style: GoogleFonts.poppins(
                  fontSize:   18,
                  fontWeight: FontWeight.bold,
                  color:      _textDark,
                )),
            const SizedBox(height: 10),
            Text('This may take 2–4 minutes on first run',
                style: GoogleFonts.poppins(
                  fontSize: 13,
                  color:    Colors.grey.shade500,
                )),
          ],
        ),
      ),
    );
  }

  // ─── Results page ─────────────────────────────────────────────────────────

  Widget _buildResultsPage() {
    return Scaffold(
      backgroundColor: _bg,
      body: Column(
        children: [
          _buildHeader(
            icon:     Icons.check_circle_outline_rounded,
            title:    'Review & Confirm',
            subtitle: 'Edit any field before confirming',
          ),
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 24),
              child: Column(
                children: [
                  _buildQualityBadge(),
                  const SizedBox(height: 20),
                  _buildResultCard(),
                  const SizedBox(height: 24),
                  _buildConfirmButton(),
                  const SizedBox(height: 12),
                  TextButton.icon(
                    onPressed: _backToOptions,
                    icon:  const Icon(Icons.refresh_rounded, size: 18, color: _primary),
                    label: Text('Try Again',
                        style: GoogleFonts.poppins(
                          color:      _primary,
                          fontWeight: FontWeight.w600,
                        )),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildQualityBadge() {
    final pct    = (_extractedCount / 6 * 100).round();
    final isGood = _extractedCount >= 4;
    final color  = isGood ? Colors.green : Colors.orange;
    final msg    = isGood
        ? '$_extractedCount/6 fields detected — great result!'
        : '$_extractedCount/6 fields detected — please check and fill empty fields';

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color:        color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(14),
        border:       Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Row(
        children: [
          Icon(
            isGood ? Icons.check_circle_rounded : Icons.warning_amber_rounded,
            color: color,
            size:  22,
          ),
          const SizedBox(width: 10),
          Expanded(
            child: Text(msg,
                style: GoogleFonts.poppins(
                    fontSize:   12,
                    color:      _textDark,
                    fontWeight: FontWeight.w500)),
          ),
          Text('$pct%',
              style: GoogleFonts.poppins(
                fontSize:   16,
                fontWeight: FontWeight.bold,
                color:      color,
              )),
        ],
      ),
    );
  }

  Widget _buildResultCard() {
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color:        Colors.white,
        borderRadius: BorderRadius.circular(20),
        boxShadow: [
          BoxShadow(
            color:      Colors.black.withValues(alpha: 0.05),
            blurRadius: 16,
            offset:     const Offset(0, 6),
          ),
        ],
      ),
      child: Column(
        children: [
          _resultField(label: 'Full Name',           icon: Icons.person_outline,       controller: _nameCtrl),
          _divider(),
          _resultField(label: 'National ID Number',  icon: Icons.badge_outlined,       controller: _idCtrl,
              keyboardType: TextInputType.number),
          _divider(),
          _resultField(label: 'Date of Birth',       icon: Icons.cake_outlined,        controller: _dobCtrl),
          _divider(),
          _resultField(label: 'Street Address',      icon: Icons.location_on_outlined, controller: _addressCtrl),
          _divider(),
          _resultField(label: 'District & Gov.',     icon: Icons.map_outlined,         controller: _districtCtrl),
          _divider(),
          _resultField(label: 'Card Serial Number',  icon: Icons.credit_card_outlined, controller: _cardNumCtrl),
        ],
      ),
    );
  }

  Widget _resultField({
    required String               label,
    required IconData             icon,
    required TextEditingController controller,
    TextInputType?                keyboardType,
  }) {
    final isEmpty = controller.text.isEmpty;
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 8),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(icon, size: 15, color: _primary),
              const SizedBox(width: 6),
              Text(label,
                  style: GoogleFonts.poppins(
                    fontSize:   11,
                    fontWeight: FontWeight.w600,
                    color:      _textMid,
                  )),
              if (isEmpty) ...[
                const SizedBox(width: 6),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                  decoration: BoxDecoration(
                    color:        Colors.orange.withValues(alpha: 0.15),
                    borderRadius: BorderRadius.circular(4),
                  ),
                  child: Text('Not detected',
                      style: GoogleFonts.poppins(
                        fontSize:   9,
                        color:      Colors.orange.shade800,
                        fontWeight: FontWeight.w600,
                      )),
                ),
              ],
            ],
          ),
          const SizedBox(height: 6),
          TextFormField(
            controller:   controller,
            keyboardType: keyboardType,
            textDirection: TextDirection.rtl,
            style: GoogleFonts.poppins(
              fontSize:   14,
              color:      _textDark,
              fontWeight: FontWeight.w500,
            ),
            decoration: InputDecoration(
              hintText:  isEmpty ? 'Tap to enter manually' : null,
              hintStyle: GoogleFonts.poppins(color: Colors.grey.shade400, fontSize: 13),
              filled:    true,
              fillColor: isEmpty
                  ? Colors.orange.withValues(alpha: 0.04)
                  : const Color(0xFFF0F7FF),
              contentPadding: const EdgeInsets.symmetric(horizontal: 14, vertical: 12),
              enabledBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10),
                borderSide: BorderSide(
                  color: isEmpty
                      ? Colors.orange.withValues(alpha: 0.4)
                      : Colors.transparent,
                ),
              ),
              focusedBorder: OutlineInputBorder(
                borderRadius: BorderRadius.circular(10),
                borderSide: const BorderSide(color: _primary, width: 1.5),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _divider() => Divider(color: Colors.grey.shade100, height: 8);

  Widget _buildConfirmButton() {
    return Container(
      width:  double.infinity,
      height: 56,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(14),
        boxShadow: [
          BoxShadow(
            color:      _primary.withValues(alpha: 0.35),
            blurRadius: 14,
            offset:     const Offset(0, 5),
          ),
        ],
      ),
      child: ElevatedButton.icon(
        onPressed: _confirm,
        style: ElevatedButton.styleFrom(
          backgroundColor: _primary,
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(14)),
          elevation: 0,
        ),
        icon:  const Icon(Icons.check_rounded, color: Colors.white, size: 22),
        label: Text('Confirm & Use These Details',
            style: GoogleFonts.poppins(
              color:      Colors.white,
              fontWeight: FontWeight.bold,
              fontSize:   15,
            )),
      ),
    );
  }

  // ─── Error page ───────────────────────────────────────────────────────────

  Widget _buildErrorPage() {
    return Scaffold(
      backgroundColor: _bg,
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 28),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Container(
                width:  100,
                height: 100,
                decoration: BoxDecoration(
                  shape: BoxShape.circle,
                  color: Colors.redAccent.withValues(alpha: 0.1),
                ),
                child: const Icon(Icons.image_search_rounded,
                    color: Colors.redAccent, size: 46),
              ),
              const SizedBox(height: 28),
              Text('Could Not Read Card',
                  textAlign: TextAlign.center,
                  style: GoogleFonts.poppins(
                    fontSize:   22,
                    fontWeight: FontWeight.bold,
                    color:      _textDark,
                  )),
              const SizedBox(height: 12),
              Text(_errorMessage,
                  textAlign: TextAlign.center,
                  style: GoogleFonts.poppins(
                    fontSize: 13,
                    color:    Colors.grey.shade600,
                    height:   1.6,
                  )),
              const SizedBox(height: 32),
              _buildTips(),
              const SizedBox(height: 32),
              SizedBox(
                width:  double.infinity,
                height: 54,
                child: ElevatedButton.icon(
                  onPressed: _backToOptions,
                  style: ElevatedButton.styleFrom(
                    backgroundColor: _primary,
                    shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(14)),
                    elevation: 0,
                  ),
                  icon:  const Icon(Icons.refresh_rounded, color: Colors.white, size: 20),
                  label: Text('Try Again',
                      style: GoogleFonts.poppins(
                        color:      Colors.white,
                        fontWeight: FontWeight.bold,
                        fontSize:   15,
                      )),
                ),
              ),
              const SizedBox(height: 12),
              TextButton(
                onPressed: () => Navigator.pop(context),
                child: Text('Skip & Fill Manually',
                    style: GoogleFonts.poppins(
                      color:      _textMid,
                      fontWeight: FontWeight.w500,
                    )),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildTips() {
    final items = [
      'Use a clear, high-resolution photo',
      'Make sure the entire card is visible',
      'Good lighting — avoid glare or shadows',
      'Hold the camera directly above the card',
    ];
    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color:        Colors.amber.withValues(alpha: 0.08),
        borderRadius: BorderRadius.circular(14),
        border:       Border.all(color: Colors.amber.withValues(alpha: 0.3)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.tips_and_updates_rounded,
                  color: Colors.amber, size: 18),
              const SizedBox(width: 8),
              Text('Tips for a better scan',
                  style: GoogleFonts.poppins(
                    fontWeight: FontWeight.w600,
                    fontSize:   13,
                    color:      _textDark,
                  )),
            ],
          ),
          const SizedBox(height: 10),
          ...items.map((tip) => Padding(
                padding: const EdgeInsets.symmetric(vertical: 3),
                child: Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    const Text('• ',
                        style: TextStyle(
                            color:      Colors.amber,
                            fontWeight: FontWeight.bold)),
                    Expanded(
                      child: Text(tip,
                          style: GoogleFonts.poppins(
                            fontSize: 12,
                            color:    _textMid,
                          )),
                    ),
                  ],
                ),
              )),
        ],
      ),
    );
  }
}
