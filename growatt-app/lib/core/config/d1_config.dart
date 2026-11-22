class D1Config {
  const D1Config({required this.accountId, required this.databaseId, required this.apiToken});

  final String accountId;
  final String databaseId;
  final String apiToken;

  static const fromEnvironment = D1Config(
    accountId: String.fromEnvironment('accountId'),
    databaseId: String.fromEnvironment('databaseId'),
    apiToken: String.fromEnvironment('apiToken'),
  );

  bool get isConfigured =>
      accountId.isNotEmpty && databaseId.isNotEmpty && apiToken.isNotEmpty;

  String get queryUrl =>
      'https://api.cloudflare.com/client/v4/accounts/$accountId/d1/database/$databaseId/query';
}

/// `--dart-define=FAKE_DATA=true` (or `old_schema`) swaps D1 for generated data.
const fakeDataMode = String.fromEnvironment('FAKE_DATA');
