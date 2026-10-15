package com.rewardassist.wakerelay;
import android.content.*;
public final class RelayRecovery extends BroadcastReceiver {
  public void onReceive(Context context,Intent intent) {
    String action=intent.getAction();
    if(!Intent.ACTION_BOOT_COMPLETED.equals(action)&&!Intent.ACTION_MY_PACKAGE_REPLACED.equals(action))return;
    if(!context.getSharedPreferences("relay",0).getBoolean("enabled",false))return;
    try {context.startForegroundService(new Intent(context,RelayService.class));}
    catch(RuntimeException error){context.getSharedPreferences("relay",0).edit().putString("status","Android blocked automatic restart. Open Wake Relay to reconnect.").apply();}
  }
}
