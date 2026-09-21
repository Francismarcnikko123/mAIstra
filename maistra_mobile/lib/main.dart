import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'screens/capture_screen.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  await Supabase.initialize(
    url: 'https://cvtshfshqccuncamvnkl.supabase.co',
    anonKey:
        'sb_publishable_JVg6v4EDytH23pzt3kYqjA_erNxp_dr',
  );

  runApp(const MyApp());
}

class MyApp extends StatelessWidget {
  const MyApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'mAIstra',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(seedColor: Colors.red),
        useMaterial3: true,
      ),
      home: const CaptureScreen(
        questionId: '3f4b3b6e-1234-4567-8910-abcdef123456',
      ),
    );
  }
}
