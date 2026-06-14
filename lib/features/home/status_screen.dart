import 'package:flutter/material.dart';
import 'package:dio/dio.dart';
import 'package:findoor_app2/core/api_config.dart';

enum AppStatus { pending, approved, rejected, other }

class StatusPage extends StatefulWidget {
  final String trackingCode;
  const StatusPage({super.key, required this.trackingCode});

  @override
  State<StatusPage> createState() => _StatusPageState();
}

class _StatusPageState extends State<StatusPage> {
  static const Color darkText = Color(0xFF263238);

  AppStatus _status      = AppStatus.pending;
  String    _statusLabel = '';
  String    _adminNotes  = '';
  bool      _isLoading   = true;
  String    _errorMsg    = '';

  @override
  void initState() {
    super.initState();
    _fetchStatus();
  }

  Future<void> _fetchStatus() async {
    setState(() { _isLoading = true; _errorMsg = ''; });
    try {
      final dio = Dio(BaseOptions(
        connectTimeout: const Duration(seconds: 15),
        receiveTimeout: const Duration(seconds: 15),
      ));
      final res = await dio.get(
        '${ApiConfig.aiBase}/api/application/track/${widget.trackingCode}',
        options: Options(headers: {'X-API-Key': ApiConfig.chatApiKey}),
      );
      if (res.statusCode == 200 && res.data['success'] == true) {
        final app    = res.data['application'] as Map<String, dynamic>;
        final raw    = app['status'] as String? ?? 'pending_review';
        final label  = app['status_label'] as String? ?? '';
        final notes  = app['admin_notes'] as String? ?? '';
        setState(() {
          _statusLabel = label;
          _adminNotes  = notes;
          _status      = _mapStatus(raw);
          _isLoading   = false;
        });
      }
    } on DioException catch (e) {
      setState(() {
        _isLoading = false;
        _errorMsg  = e.type == DioExceptionType.connectionError
            ? 'Cannot reach server.'
            : (e.response?.data?['detail'] as String? ?? 'Could not load status.');
      });
    }
  }

  AppStatus _mapStatus(String raw) {
    switch (raw) {
      case 'approved':        return AppStatus.approved;
      case 'rejected':        return AppStatus.rejected;
      case 'pending_review':
      case 'awaiting_docs':   return AppStatus.pending;
      default:                return AppStatus.other;
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF8FAFC),
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 0.5,
        centerTitle: true,
        leading: IconButton(
          icon: const Icon(Icons.arrow_back_ios_new, color: darkText, size: 20),
          onPressed: () => Navigator.pop(context),
        ),
        title: const Text('Application Status',
            style: TextStyle(color: darkText, fontWeight: FontWeight.bold, fontSize: 18)),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh_rounded, color: darkText),
            onPressed: _fetchStatus,
            tooltip: 'Refresh',
          ),
        ],
      ),
      body: _isLoading
          ? const Center(child: CircularProgressIndicator(color: Color(0xFF1E88E5)))
          : _errorMsg.isNotEmpty
              ? _buildError()
              : SingleChildScrollView(
                  padding: const EdgeInsets.all(24),
                  child: Column(
                    children: [
                      _buildStatusCard(),
                      const SizedBox(height: 24),
                      _buildTrackingCode(),
                      if (_adminNotes.isNotEmpty) ...[
                        const SizedBox(height: 16),
                        _buildNotesCard(),
                      ],
                      const SizedBox(height: 32),
                      _buildDescription(),
                      const SizedBox(height: 40),
                      _buildActionButton(context),
                    ],
                  ),
                ),
    );
  }

  Widget _buildError() => Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const Icon(Icons.error_outline_rounded, color: Colors.redAccent, size: 60),
            const SizedBox(height: 16),
            Text(_errorMsg, textAlign: TextAlign.center,
                style: const TextStyle(color: Colors.grey, fontSize: 15)),
            const SizedBox(height: 24),
            ElevatedButton.icon(
              onPressed: _fetchStatus,
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
              style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF1E88E5)),
            ),
          ],
        ),
      );

  Widget _buildStatusCard() {
    final (color, icon, label) = switch (_status) {
      AppStatus.approved => (Colors.green.shade600,  Icons.check_circle_rounded,    'Approved'),
      AppStatus.rejected => (Colors.red.shade600,    Icons.cancel_rounded,          'Rejected'),
      AppStatus.pending  => (Colors.orange.shade600, Icons.hourglass_empty_rounded, 'Under Review'),
      AppStatus.other    => (Colors.blueGrey,        Icons.help_outline_rounded,    _statusLabel),
    };

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(vertical: 40, horizontal: 20),
      decoration: BoxDecoration(
        color: color,
        borderRadius: BorderRadius.circular(28),
        boxShadow: [BoxShadow(color: color.withValues(alpha: 0.3), blurRadius: 15, offset: const Offset(0, 8))],
      ),
      child: Column(
        children: [
          Icon(icon, color: Colors.white, size: 70),
          const SizedBox(height: 16),
          Text(label,
              style: const TextStyle(fontSize: 26, fontWeight: FontWeight.bold,
                  color: Colors.white, letterSpacing: 1)),
          if (_statusLabel.isNotEmpty) ...[
            const SizedBox(height: 8),
            Text(_statusLabel,
                style: const TextStyle(color: Colors.white70, fontSize: 14)),
          ],
        ],
      ),
    );
  }

  Widget _buildTrackingCode() => Container(
        padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
        decoration: BoxDecoration(
          color: Colors.white,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: Colors.grey.shade200),
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.confirmation_number_outlined, size: 18, color: Color(0xFF1E88E5)),
            const SizedBox(width: 8),
            Text('Tracking Code: ',
                style: TextStyle(color: Colors.grey.shade600, fontSize: 14)),
            Text(widget.trackingCode,
                style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14,
                    color: Color(0xFF1E88E5), letterSpacing: 1.5)),
          ],
        ),
      );

  Widget _buildNotesCard() => Container(
        width: double.infinity,
        padding: const EdgeInsets.all(16),
        decoration: BoxDecoration(
          color: Colors.amber.shade50,
          borderRadius: BorderRadius.circular(12),
          border: Border.all(color: Colors.amber.shade200),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(Icons.info_outline_rounded, color: Colors.amber.shade700, size: 20),
            const SizedBox(width: 10),
            Expanded(
              child: Text(_adminNotes,
                  style: TextStyle(color: Colors.amber.shade900, fontSize: 14, height: 1.4)),
            ),
          ],
        ),
      );

  Widget _buildDescription() {
    final (title, sub) = switch (_status) {
      AppStatus.pending  => ('Under Official Review',
          'A government officer is currently verifying your documents and eligibility.'),
      AppStatus.approved => ('Ready for Contract',
          'Your application was accepted. Please proceed to the housing office for next steps.'),
      AppStatus.rejected => ('Review Declined',
          'Your application was not approved at this time. You may re-apply or contact support.'),
      AppStatus.other    => ('Status Updated', 'Please check back later for more details.'),
    };
    return Column(
      children: [
        Text(title, style: const TextStyle(fontSize: 20, fontWeight: FontWeight.bold, color: darkText)),
        const SizedBox(height: 12),
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 10),
          child: Text(sub,
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 15, color: Colors.grey.shade600, height: 1.5)),
        ),
      ],
    );
  }

  Widget _buildActionButton(BuildContext context) {
    final (label, color, icon) = switch (_status) {
      AppStatus.approved => ('Choose Your Unit',    Colors.green.shade700, Icons.home_work_rounded),
      AppStatus.rejected => ('Back to Home',        Colors.red.shade700,   Icons.home_rounded),
      _                  => ('Back to Home',        Colors.blueGrey,       Icons.home_rounded),
    };
    return SizedBox(
      width: double.infinity,
      child: ElevatedButton.icon(
        onPressed: () => Navigator.popUntil(context, (r) => r.isFirst),
        icon: Icon(icon, color: Colors.white),
        label: Text(label,
            style: const TextStyle(color: Colors.white, fontWeight: FontWeight.bold, fontSize: 16)),
        style: ElevatedButton.styleFrom(
          backgroundColor: color,
          padding: const EdgeInsets.symmetric(vertical: 20),
          shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(16)),
          elevation: 0,
        ),
      ),
    );
  }
}
