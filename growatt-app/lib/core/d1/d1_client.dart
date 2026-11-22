import 'package:dio/dio.dart';
import 'package:growatt_app/core/config/d1_config.dart';
import 'package:growatt_app/core/d1/d1_source.dart';

class D1Client implements D1Source {
  D1Client(this.config, {Dio? dio})
      : _dio = dio ??
            Dio(BaseOptions(
              connectTimeout: const Duration(seconds: 15),
              receiveTimeout: const Duration(seconds: 15),
            ));

  final D1Config config;
  final Dio _dio;

  @override
  Future<List<D1Row>> query(String sql, [List<Object?> params = const []]) async {
    final Response<dynamic> response;
    try {
      response = await _dio.post<dynamic>(
        config.queryUrl,
        data: {'sql': sql, 'params': params},
        options: Options(
          headers: {'Authorization': 'Bearer ${config.apiToken}'},
          contentType: Headers.jsonContentType,
          responseType: ResponseType.json,
          // Cloudflare reports SQL errors with 4xx bodies we still want to read.
          validateStatus: (_) => true,
        ),
      );
    } on DioException catch (e) {
      throw D1Exception(_networkMessage(e));
    }
    return parseD1Response(response.data, response.statusCode ?? 0);
  }

  static String _networkMessage(DioException e) => switch (e.type) {
        DioExceptionType.connectionTimeout ||
        DioExceptionType.sendTimeout ||
        DioExceptionType.receiveTimeout =>
          'D1 request timed out',
        DioExceptionType.connectionError => 'No connection to Cloudflare',
        _ => 'D1 request failed',
      };
}

/// The old worker schema lacks `worker_state`, `events` and the newer
/// snapshot columns; those queries count as empty rather than failing.
bool isMissingSchemaError(String message) {
  final m = message.toLowerCase();
  return m.contains('no such table') || m.contains('no such column');
}

List<D1Row> parseD1Response(Object? body, int statusCode) {
  if (body is Map && body['success'] == true) {
    final result = body['result'];
    if (result is List && result.isNotEmpty && result.first is Map) {
      final rows = (result.first as Map)['results'];
      if (rows is List) {
        return [for (final r in rows) if (r is Map) Map<String, dynamic>.from(r)];
      }
    }
    return [];
  }
  String? message;
  if (body is Map && body['errors'] is List) {
    for (final e in body['errors'] as List) {
      if (e is Map && e['message'] is String) {
        message = e['message'] as String;
        break;
      }
    }
  }
  if (message != null) {
    if (isMissingSchemaError(message)) return [];
    throw D1Exception(message);
  }
  throw D1Exception('D1 returned HTTP $statusCode');
}
