import 'package:flutter/material.dart';

class AppRadii {
  AppRadii._();

  static const double xs = 8;
  static const double sm = 12;
  static const double md = 16;
  static const double lg = 20;
  static const double xl = 24;
  static const double full = 999;

  static const BorderRadius xsBr = BorderRadius.all(Radius.circular(xs));
  static const BorderRadius smBr = BorderRadius.all(Radius.circular(sm));
  static const BorderRadius mdBr = BorderRadius.all(Radius.circular(md));
  static const BorderRadius lgBr = BorderRadius.all(Radius.circular(lg));
  static const BorderRadius xlBr = BorderRadius.all(Radius.circular(xl));
  static const BorderRadius fullBr = BorderRadius.all(Radius.circular(full));
}
