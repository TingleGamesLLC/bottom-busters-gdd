using System.Collections.Generic;
using UnityEngine;

/// <summary>Character Select: one tile per character skin, drawn with OnGUI.</summary>
public class CharacterSelect : MonoBehaviour
{
    private readonly List<string> skins = new List<string> { "player", "player2", "player3" };
    private int picked;

    private void OnGUI()
    {
        for (int i = 0; i < skins.Count; i++)
        {
            Rect tile = new Rect(20 + i * 110, 40, 100, 100);
            if (GUI.Button(tile, skins[i])) picked = i;
            CharacterNameDisplay.DrawUnder(tile, skins[i]);
        }
    }

    public string PickedSkin => skins[picked];
}
