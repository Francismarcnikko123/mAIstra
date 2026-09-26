import 'package:flutter/material.dart';
import 'package:supabase_flutter/supabase_flutter.dart';
import 'screens/question_picker_screen.dart';
import 'theme/app_theme.dart';

void main() async {
  WidgetsFlutterBinding.ensureInitialized();

  await Supabase.initialize(
    url: 'https://cvtshfshqccuncamvnkl.supabase.co',
    anonKey: 'sb_publishable_JVg6v4EDytH23pzt3kYqjA_erNxp_dr',
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
      theme: buildAppTheme(Brightness.light),
      darkTheme: buildAppTheme(Brightness.dark),
      home: const QuestionPickerScreen(),
    );
  }
}
