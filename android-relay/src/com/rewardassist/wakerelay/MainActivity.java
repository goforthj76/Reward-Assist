package com.rewardassist.wakerelay;
import android.app.*;
import android.os.*;
import android.content.*;
import android.graphics.Color;
import android.widget.*;
import android.text.InputType;
public class MainActivity extends Activity {
  private TextView status; private final Handler handler=new Handler();
  private final Runnable update=new Runnable(){public void run(){status.setText(getSharedPreferences("relay",0).getString("status","Not started"));handler.postDelayed(this,2000);}};
  public void onCreate(Bundle saved) {
    super.onCreate(saved);
    LinearLayout box=new LinearLayout(this);box.setOrientation(1);box.setPadding(32,48,32,24);box.setBackgroundColor(Color.rgb(242,245,252));
    ScrollView scroll=new ScrollView(this);scroll.addView(box);setContentView(scroll);
    TextView title=new TextView(this);title.setText("Wake your computer\nReward Assist");title.setTextSize(28);title.setTextColor(Color.rgb(22,35,64));box.addView(title);
    TextView intro=new TextView(this);intro.setText("Leave this tablet on your home Wi-Fi with its screen off. It can only send a wake signal to the computer you configure below. No wallet or restaurant passwords are needed.\n\nCreate a tablet pairing key on your iPhone under Computer tasks → Wake from anywhere. Paste it here.");intro.setPadding(0,24,0,24);box.addView(intro);
    android.content.SharedPreferences prefs=getSharedPreferences("relay",0);
    EditText key=new EditText(this);key.setHint("Pairing key");key.setInputType(InputType.TYPE_CLASS_TEXT|InputType.TYPE_TEXT_VARIATION_PASSWORD);box.addView(key);
    TextView savedKey=new TextView(this);savedKey.setText(prefs.contains("token")?"Pairing key saved. Leave blank to keep it.":"No pairing key saved.");box.addView(savedKey);
    EditText mac=new EditText(this);mac.setHint("Computer MAC address");mac.setSingleLine();mac.setText(prefs.getString("mac",""));box.addView(mac);
    Button start=new Button(this);start.setText("Enable wake relay");box.addView(start);
    start.setOnClickListener(v->{
      try {
        String address=mac.getText().toString().trim();WakePacket.create(address);
        String token=key.getText().toString().trim();if(token.isEmpty())token=prefs.getString("token","");
        if(!token.matches("(?i)[a-f0-9-]{36}\\.[a-f0-9]{64}"))throw new IllegalArgumentException("Paste the pairing key from your iPhone.");
        prefs.edit().putString("token",token).putString("mac",address).putBoolean("enabled",true).apply();key.setText("");savedKey.setText("Pairing key saved on this tablet.");
        if(Build.VERSION.SDK_INT>=33 && checkSelfPermission("android.permission.POST_NOTIFICATIONS")!=android.content.pm.PackageManager.PERMISSION_GRANTED)requestPermissions(new String[]{"android.permission.POST_NOTIFICATIONS"},1);
        startForegroundService(new Intent(this,RelayService.class));
      }catch(Exception e){status.setText(e.getMessage());}
    });
    Button stop=new Button(this);stop.setText("Stop relay");box.addView(stop);stop.setOnClickListener(v->{prefs.edit().putBoolean("enabled",false).putString("status","Stopped. Remote wake is disabled.").apply();stopService(new Intent(this,RelayService.class));});
    status=new TextView(this);status.setPadding(0,24,0,24);box.addView(status);
    Button battery=new Button(this);battery.setText("Open battery settings");box.addView(battery);
    battery.setOnClickListener(v->{try{startActivity(new Intent(android.provider.Settings.ACTION_IGNORE_BATTERY_OPTIMIZATION_SETTINGS));}catch(Exception e){startActivity(new Intent(android.provider.Settings.ACTION_APPLICATION_DETAILS_SETTINGS,android.net.Uri.parse("package:"+getPackageName())));}});
    TextView batteryHelp=new TextView(this);batteryHelp.setText("For remote wake, set this app to Unrestricted / Don't optimize in Android battery settings. Keep the tablet plugged into a charger that stays powered while the PC sleeps. Screen off is fine. Force-stopping the app prevents automatic recovery.");box.addView(batteryHelp);
    TextView help=new TextView(this);help.setText("Keep the tablet charged. The relay checks for requests every 20 seconds. Android may suspend it; verify it stays online with the screen off. After restarting the tablet, open this app and enable the relay again.\n\nA sent wake signal is not proof the PC woke up. The iPhone waits for Reward Assist on the PC to reconnect. Nothing here switches off power or bypasses Windows sign-in.");box.addView(help);
  }
  protected void onResume(){super.onResume();if(getSharedPreferences("relay",0).getBoolean("enabled",false)){try{startForegroundService(new Intent(this,RelayService.class));}catch(Exception e){getSharedPreferences("relay",0).edit().putString("status","Could not restart relay. Tap Enable wake relay.").apply();}}handler.post(update);}
  protected void onPause(){handler.removeCallbacks(update);super.onPause();}
}
