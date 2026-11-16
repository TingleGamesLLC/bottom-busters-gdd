using UnityEngine;

/// <summary>The main menu: a PLAY button that starts a run.</summary>
public class MainMenu : MonoBehaviour
{
    public bool playing;

    private void OnGUI()
    {
        if (!playing && GUI.Button(new Rect(20, 200, 200, 60), "PLAY")) StartRun();
        if (!playing) BestScoreManager.DrawMenuLabel();
    }

    public void StartRun()
    {
        playing = true;
    }
}
