typedef D1Row = Map<String, dynamic>;

abstract interface class D1Source {
  Future<List<D1Row>> query(String sql, [List<Object?> params = const []]);
}

class D1Exception implements Exception {
  const D1Exception(this.message);
  final String message;

  @override
  String toString() => message;
}
